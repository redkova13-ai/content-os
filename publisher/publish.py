#!/usr/bin/env python3
"""Publish one post (a "slot") to Instagram, Threads, VK and Telegram.

usage: publish.py SLOT_JSON [--publish --approval APPROVED.json] [--only ig,tg,vk,threads]

Without --publish this is a DRY RUN: everything is validated, Instagram/Threads containers are
created and waited on (they stay invisible until media_publish/threads_publish, which is not
called), VK photos/docs are uploaded privately (wall.post is not called), Telegram requests are
built but not sent. A JSON report per platform is printed.

--publish needs a GATE 2 approval JSON whose asset_id matches the slot. Platforms then go out
in the order ig, threads, vk, tg; a failure on one does not stop the others.

Auth: Instagram, Threads and VK tokens are injected by the network proxy and never passed here.
Telegram reads TELEGRAM_BOT_TOKEN from the environment; it is never printed.
See publisher/README.md for the SLOT_JSON format.
"""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

import requests
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
RAW = 'https://raw.githubusercontent.com/redkova13-ai/content-os/main/'

IG_GRAPH = 'https://graph.facebook.com/v21.0'
IG_USER = '17841402153358869'  # @irg_psy
TH_GRAPH = 'https://graph.threads.net/v1.0'
TH_USER = '28685339387816848'  # threads @irg_psy
VK_API = 'https://api.vk.com/method'
VK_V = '5.199'
VK_GROUP = 235951709
VK_OWNER = -VK_GROUP
TG_API = 'https://api.telegram.org'
TG_CHAT = '-1002550616198'

ORDER = ['ig', 'threads', 'vk', 'tg']
KINDS = {'carousel', 'image', 'reels', 'story', 'text'}
LIMITS = {'ig_caption': 2200, 'ig_hashtags': 30, 'tg_text': 4096, 'tg_caption': 1024,
          'vk_text': 16000, 'threads_text': 500}
MB = 1024 * 1024


class Fail(Exception):
    pass


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- slot loading / validation

def load_slot(path):
    path = Path(path).resolve()
    slot = json.loads(path.read_text(encoding='utf-8'))
    base = path.parent

    def p(v):
        if not v:
            return None
        q = Path(v).expanduser()
        return q if q.is_absolute() else (base / q).resolve()

    media = slot.get('media') or {}
    s = {
        'asset_id': slot.get('asset_id'),
        'kind': slot.get('kind'),
        'slides_dir': p(media.get('slides_dir')),
        'image': p(media.get('image')),
        'video': p(media.get('video')),
        'cover': p(media.get('cover')),
        'document': p(media.get('document')),
        'platforms': {},
    }
    for k in ORDER:
        if k in slot and slot[k] is not None:
            cfg = dict(slot[k])
            for f in ('caption_file', 'text_file', 'first_comment_file'):
                if cfg.get(f):
                    cfg[f] = p(cfg[f])
            s['platforms'][k] = cfg
    return s


def read_text(cfg, file_key, inline_key):
    if cfg.get(file_key):
        f = cfg[file_key]
        if not f.is_file():
            raise Fail(f'{file_key} not found: {f}')
        return f.read_text(encoding='utf-8').strip()
    return (cfg.get(inline_key) or '').strip()


def need_file(path, what, max_mb=None, exts=None):
    if not path:
        raise Fail(f'{what} is required for this kind')
    if not path.is_file():
        raise Fail(f'{what} not found: {path}')
    if exts and path.suffix.lower() not in exts:
        raise Fail(f'{what} must be {"/".join(exts)}: {path.name}')
    if max_mb and path.stat().st_size > max_mb * MB:
        raise Fail(f'{what} is {path.stat().st_size / MB:.1f} MB, limit {max_mb} MB: {path.name}')
    return path


def slides(s, lo, hi):
    d = s['slides_dir']
    if not d or not d.is_dir():
        raise Fail(f'slides_dir not found: {d}')
    pngs = sorted(d.glob('slide_*.png')) or sorted(d.glob('slide_*.jpg'))
    if not lo <= len(pngs) <= hi:
        raise Fail(f'carousel needs {lo}–{hi} slides, found {len(pngs)} in {d}')
    return pngs


def visual(s):
    """The single still image used for kinds image/story."""
    return need_file(s['image'], 'media.image', exts={'.png', '.jpg', '.jpeg'})


def plan_ig(s, cfg):
    pl = _plan_ig(s, cfg)
    comment = read_text(cfg, 'first_comment_file', 'first_comment')
    if cfg.get('first_comment_file') or cfg.get('first_comment'):
        if not comment:
            raise Fail('IG first comment is empty')
        if len(comment) > LIMITS['ig_caption']:
            raise Fail(f'IG first comment is {len(comment)} chars, limit {LIMITS["ig_caption"]}')
        if s['kind'] == 'story':
            raise Fail('stories cannot have a first comment')
        pl['first_comment'] = comment
    return pl


def _plan_ig(s, cfg):
    kind = s['kind']
    cap = read_text(cfg, 'caption_file', 'caption')
    if len(cap) > LIMITS['ig_caption']:
        raise Fail(f'IG caption is {len(cap)} chars, limit {LIMITS["ig_caption"]}')
    if cap.count('#') > LIMITS['ig_hashtags']:
        raise Fail(f'IG caption has {cap.count("#")} hashtags, limit {LIMITS["ig_hashtags"]}')
    if kind == 'carousel':
        return {'kind': kind, 'caption': cap, 'slides': slides(s, 2, 10)}
    if kind == 'image':
        return {'kind': kind, 'caption': cap, 'image': visual(s)}
    if kind == 'story':
        return {'kind': kind, 'image': visual(s)}  # stories carry no caption
    if kind == 'reels':
        v = need_file(s['video'], 'media.video', max_mb=1000, exts={'.mp4', '.mov'})
        c = need_file(s['cover'], 'media.cover', exts={'.png', '.jpg', '.jpeg'}) if s['cover'] else None
        return {'kind': kind, 'caption': cap, 'video': v, 'cover': c}
    raise Fail(f'Instagram has no "{kind}" post type')


def plan_threads(s, cfg):
    kind = s['kind']
    text = read_text(cfg, 'text_file', 'text')
    if len(text) > LIMITS['threads_text']:
        raise Fail(f'Threads text is {len(text)} chars, limit {LIMITS["threads_text"]}')
    if kind == 'text':
        if not text:
            raise Fail('Threads text post needs text')
        return {'kind': 'text', 'text': text}
    if kind == 'carousel':
        return {'kind': 'carousel', 'text': text, 'slides': slides(s, 2, 20)}
    if kind in ('image', 'story'):
        return {'kind': 'image', 'text': text, 'image': visual(s)}
    if kind == 'reels':
        return {'kind': 'video', 'text': text, 'video': need_file(s['video'], 'media.video', 1000, {'.mp4', '.mov'})}


def plan_vk(s, cfg):
    kind = s['kind']
    text = read_text(cfg, 'text_file', 'text')
    if len(text) > LIMITS['vk_text']:
        raise Fail(f'VK text is {len(text)} chars, limit {LIMITS["vk_text"]}')
    photos, notes = [], []
    if kind == 'carousel':
        photos = slides(s, 1, 10)
    elif kind in ('image', 'story'):
        photos = [visual(s)]
    elif kind == 'reels':
        if s['cover']:
            photos = [need_file(s['cover'], 'media.cover', exts={'.png', '.jpg', '.jpeg'})]
        else:
            notes.append('reels without media.cover: VK gets text only')
        notes.append('VK video upload needs a user token: VK gets the cover + text')
    doc = None
    if cfg.get('attach_document', True) and s['document']:
        doc = need_file(s['document'], 'media.document', max_mb=200)
    if len(photos) + (1 if doc else 0) > 10:
        raise Fail(f'VK allows 10 attachments, slot has {len(photos)} photos + {"1 doc" if doc else "no doc"}')
    if not text and not photos and not doc:
        raise Fail('VK post would be empty')
    return {'kind': kind, 'text': text, 'photos': photos, 'document': doc, 'notes': notes}


def plan_tg(s, cfg):
    kind = s['kind']
    text = read_text(cfg, 'text_file', 'text')
    if len(text) > LIMITS['tg_text']:
        raise Fail(f'Telegram text is {len(text)} chars, limit {LIMITS["tg_text"]}')
    steps = []  # (method, data, files{field: path})
    msg = ('sendMessage', {'chat_id': TG_CHAT, 'text': text,
                           'link_preview_options': json.dumps({'is_disabled': True})}, {})
    if kind == 'carousel':
        ph = [need_file(p, 'slide', max_mb=10) for p in slides(s, 2, 10)]
        media = [{'type': 'photo', 'media': f'attach://p{i}'} for i in range(len(ph))]
        steps.append(('sendMediaGroup', {'chat_id': TG_CHAT, 'media': json.dumps(media)},
                      {f'p{i}': p for i, p in enumerate(ph)}))
        if text:
            steps.append(msg)
    elif kind in ('image', 'story'):
        img = need_file(visual(s), 'media.image', max_mb=10)
        if len(text) <= LIMITS['tg_caption']:
            d = {'chat_id': TG_CHAT}
            if text:
                d['caption'] = text
            steps.append(('sendPhoto', d, {'photo': img}))
        else:
            steps += [('sendPhoto', {'chat_id': TG_CHAT}, {'photo': img}), msg]
    elif kind == 'reels':
        v = need_file(s['video'], 'media.video', max_mb=50, exts={'.mp4'})
        steps.append(('sendVideo', {'chat_id': TG_CHAT, 'supports_streaming': 'true'}, {'video': v}))
        if text:
            steps.append(msg)
    elif kind == 'text':
        if not text:
            raise Fail('Telegram text post needs text')
        steps.append(msg)
    if cfg.get('attach_document') and s['document']:
        doc = need_file(s['document'], 'media.document', max_mb=50)
        steps.append(('sendDocument', {'chat_id': TG_CHAT}, {'document': doc}))
    elif cfg.get('attach_document'):
        raise Fail('tg.attach_document is set but media.document is missing')
    return {'kind': kind, 'steps': steps}


PLANNERS = {'ig': plan_ig, 'threads': plan_threads, 'vk': plan_vk, 'tg': plan_tg}


# ---------------------------------------------------------------- public hosting (repo raw)

def host(asset_id, files):
    """files: {published name: local path}. Images become JPEG; returns {name: raw url}."""
    dest = REPO / 'media' / asset_id
    dest.mkdir(parents=True, exist_ok=True)
    for name, src in files.items():
        if name.endswith('.jpg'):
            Image.open(src).convert('RGB').save(dest / name, quality=92, optimize=True)
        else:
            shutil.copyfile(src, dest / name)
    git = ['git', '-C', str(REPO), '-c', 'user.name=redkova13-ai',
           '-c', 'user.email=redkova13-ai@users.noreply.github.com']
    subprocess.run(git + ['add', str(dest)], check=True)
    if subprocess.run(git + ['diff', '--cached', '--quiet']).returncode:
        subprocess.run(git + ['commit', '-qm', f'media: {asset_id}', '--', str(dest)], check=True)
        if subprocess.run(git + ['push', '-q', 'origin', 'HEAD:main']).returncode:
            subprocess.run(git + ['pull', '-q', '--rebase', 'origin', 'main'], check=True)
            subprocess.run(git + ['push', '-q', 'origin', 'HEAD:main'], check=True)
    urls = {n: RAW + f'media/{asset_id}/{n}' for n in files}
    for u in urls.values():  # raw CDN can lag a few seconds after push
        for _ in range(30):
            try:
                if requests.head(u, timeout=20).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(3)
        else:
            raise Fail(f'hosted file not reachable: {u}')
    return urls


def hosting_needs(plans):
    """Which local files Instagram/Threads must fetch by URL."""
    need = {}
    for k in ('ig', 'threads'):
        pl = plans.get(k)
        if not pl:
            continue
        for p in pl.get('slides', []):
            need[p.stem + '.jpg'] = p
        if pl.get('image'):
            need['image.jpg'] = pl['image']
        if pl.get('cover'):
            need['cover.jpg'] = pl['cover']
        if k == 'threads' and pl.get('video'):
            need['video' + pl['video'].suffix.lower()] = pl['video']
    return need


# ---------------------------------------------------------------- Meta Graph (IG + Threads)

def graph(base, method, path, **params):
    r = requests.request(method, f'{base}/{path}', params=params if method == 'GET' else None,
                         data=params if method == 'POST' else None, timeout=120)
    try:
        body = r.json()
    except ValueError:
        body = {'raw': r.text[:300]}
    if r.status_code >= 400 or 'error' in body:
        raise Fail(f'{base.split("/")[2]} {path}: HTTP {r.status_code} {json.dumps(body, ensure_ascii=False)[:500]}')
    return body


def wait_container(base, cid, field, tries=60, pause=5):
    for _ in range(tries):
        fields = 'status_code,status' if field == 'status_code' else 'status,error_message'
        st = graph(base, 'GET', cid, fields=fields)
        code = st.get(field)
        if code == 'FINISHED':
            return code
        if code in ('ERROR', 'EXPIRED'):
            raise Fail(f'container {cid}: {st}')
        time.sleep(pause)
    raise Fail(f'container {cid} not ready after {tries * pause}s')


def ig_reels_container(pl, urls):
    params = {'media_type': 'REELS', 'upload_type': 'resumable', 'caption': pl['caption'],
              'share_to_feed': 'true'}
    if pl.get('cover'):
        params['cover_url'] = urls['cover.jpg']
    c = graph(IG_GRAPH, 'POST', f'{IG_USER}/media', **params)
    data = pl['video'].read_bytes()
    r = requests.post(c['uri'], data=data, timeout=600,
                      headers={'offset': '0', 'file_size': str(len(data))})
    if r.status_code >= 400:
        raise Fail(f'rupload: HTTP {r.status_code} {r.text[:300]}')
    return c['id'], len(data)


def run_ig(pl, urls, publish):
    rep = {'kind': pl['kind']}
    if pl['kind'] == 'carousel':
        kids = [graph(IG_GRAPH, 'POST', f'{IG_USER}/media', image_url=urls[p.stem + '.jpg'],
                      is_carousel_item='true')['id'] for p in pl['slides']]
        for k in kids:
            wait_container(IG_GRAPH, k, 'status_code')
        cid = graph(IG_GRAPH, 'POST', f'{IG_USER}/media', media_type='CAROUSEL',
                    children=','.join(kids), caption=pl['caption'])['id']
        rep['children'] = kids
    elif pl['kind'] == 'image':
        cid = graph(IG_GRAPH, 'POST', f'{IG_USER}/media', image_url=urls['image.jpg'], caption=pl['caption'])['id']
    elif pl['kind'] == 'story':
        cid = graph(IG_GRAPH, 'POST', f'{IG_USER}/media', media_type='STORIES', image_url=urls['image.jpg'])['id']
    else:  # reels
        cid, size = ig_reels_container(pl, urls)
        rep['uploaded_bytes'] = size
    rep['container'] = cid
    rep['container_status'] = wait_container(IG_GRAPH, cid, 'status_code', tries=120)
    if publish:
        mid = graph(IG_GRAPH, 'POST', f'{IG_USER}/media_publish', creation_id=cid)['id']
        info = graph(IG_GRAPH, 'GET', mid, fields='permalink,timestamp')
        rep.update(media_id=mid, permalink=info.get('permalink'))
        if pl.get('first_comment'):
            try:  # the post is already live: a failed comment is reported, not fatal
                rep['first_comment_id'] = graph(IG_GRAPH, 'POST', f'{mid}/comments', message=pl['first_comment'])['id']
            except (Fail, requests.RequestException) as e:
                rep['first_comment_error'] = str(e)
    elif pl.get('first_comment'):
        rep['first_comment'] = f'validated, {len(pl["first_comment"])} chars (posted only after a real publish)'
    return rep


def run_threads(pl, urls, publish):
    rep = {'kind': pl['kind']}
    base = f'{TH_USER}/threads'
    text = {'text': pl['text']} if pl['text'] else {}
    if pl['kind'] == 'text':
        cid = graph(TH_GRAPH, 'POST', base, media_type='TEXT', **text)['id']
    elif pl['kind'] == 'image':
        cid = graph(TH_GRAPH, 'POST', base, media_type='IMAGE', image_url=urls['image.jpg'], **text)['id']
    elif pl['kind'] == 'video':
        cid = graph(TH_GRAPH, 'POST', base, media_type='VIDEO',
                    video_url=urls['video' + pl['video'].suffix.lower()], **text)['id']
    else:  # carousel
        kids = [graph(TH_GRAPH, 'POST', base, media_type='IMAGE', image_url=urls[p.stem + '.jpg'],
                      is_carousel_item='true')['id'] for p in pl['slides']]
        for k in kids:
            wait_container(TH_GRAPH, k, 'status')
        cid = graph(TH_GRAPH, 'POST', base, media_type='CAROUSEL', children=','.join(kids), **text)['id']
        rep['children'] = kids
    rep['container'] = cid
    rep['container_status'] = wait_container(TH_GRAPH, cid, 'status', tries=120)
    if publish:
        mid = graph(TH_GRAPH, 'POST', f'{TH_USER}/threads_publish', creation_id=cid)['id']
        info = graph(TH_GRAPH, 'GET', mid, fields='permalink,timestamp')
        rep.update(media_id=mid, permalink=info.get('permalink'))
    return rep


# ---------------------------------------------------------------- VK

def vk(method, **params):
    r = requests.post(f'{VK_API}/{method}', data={**params, 'v': VK_V}, timeout=120)
    body = r.json()
    if 'error' in body:
        e = body['error']
        raise Fail(f'VK {method}: {e.get("error_code")} {e.get("error_msg")}')
    return body['response']


def vk_upload(url, field, path):
    with open(path, 'rb') as f:
        r = requests.post(url, files={field: (path.name, f)}, timeout=300)
    body = r.json()
    if 'error' in body:
        raise Fail(f'VK upload {path.name}: {body}')
    return body


def run_vk(pl, publish):
    rep = {'kind': pl['kind'], 'notes': pl['notes']}
    atts = []
    if pl['photos']:
        for p in pl['photos']:
            for attempt in range(4):  # pu.vk.com now and then answers with an empty "photo"
                up = vk('photos.getMessagesUploadServer', peer_id=0)['upload_url']
                u = vk_upload(up, 'photo', p)
                if u.get('photo') not in (None, '', '[]'):
                    break
                time.sleep(2 + 2 * attempt)
            else:
                raise Fail(f'VK upload of {p.name} kept returning an empty photo')
            ph = vk('photos.saveMessagesPhoto', photo=u['photo'], server=u['server'], hash=u['hash'])[0]
            atts.append(f'photo{ph["owner_id"]}_{ph["id"]}' + (f'_{ph["access_key"]}' if ph.get('access_key') else ''))
    if pl['document']:
        up = vk('docs.getWallUploadServer', group_id=VK_GROUP)['upload_url']
        u = vk_upload(up, 'file', pl['document'])
        d = vk('docs.save', file=u['file'], title=pl['document'].name)
        d = d.get('doc', d)
        atts.append(f'doc{d["owner_id"]}_{d["id"]}' + (f'_{d["access_key"]}' if d.get('access_key') else ''))
    rep['attachments'] = atts
    rep['message_chars'] = len(pl['text'])
    if publish:
        params = {'owner_id': VK_OWNER, 'from_group': 1, 'message': pl['text']}
        if atts:
            params['attachments'] = ','.join(atts)
        pid = vk('wall.post', **params)['post_id']
        rep.update(post_id=pid, url=f'https://vk.com/wall{VK_OWNER}_{pid}')
    return rep


# ---------------------------------------------------------------- Telegram

def tg_request(token, method, data, files):
    """Build (not send) a Telegram Bot API request; file handles are opened here."""
    fh = {k: (p.name, open(p, 'rb')) for k, p in files.items()}
    req = requests.Request('POST', f'{TG_API}/bot{token}/{method}', data=data, files=fh or None)
    return req.prepare(), fh


def run_tg(pl, publish):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if publish and not token:
        raise Fail('TELEGRAM_BOT_TOKEN is not set')
    token = token or '0000000000:DRYRUN-PLACEHOLDER-TOKEN'
    rep = {'kind': pl['kind'], 'steps': []}
    for method, data, files in pl['steps']:
        prep, fh = tg_request(token, method, data, files)
        try:
            step = {'method': method, 'files': [p.name for p in files.values()],
                    'body_bytes': len(prep.body or b''),
                    'text_chars': len(data.get('text', data.get('caption', '')))}
            if publish:
                r = requests.Session().send(prep, timeout=300)
                body = r.json()
                if not body.get('ok'):
                    raise Fail(f'Telegram {method}: {body.get("error_code")} {body.get("description")}')
                res = body['result']
                step['message_ids'] = [m['message_id'] for m in res] if isinstance(res, list) else [res['message_id']]
            rep['steps'].append(step)
        finally:
            for _, f in fh.values():
                f.close()
    return rep


# ---------------------------------------------------------------- main

def redact(msg):
    tok = os.environ.get('TELEGRAM_BOT_TOKEN')
    return msg.replace(tok, '<TELEGRAM_BOT_TOKEN>') if tok else msg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('slot')
    ap.add_argument('--publish', action='store_true', help='actually post (needs --approval)')
    ap.add_argument('--approval', help='GATE 2 approval JSON: {"asset_id":..., "approved_by":..., "approved_at":...}')
    ap.add_argument('--only', help='comma list of platforms: ig,threads,vk,tg')
    a = ap.parse_args()

    s = load_slot(a.slot)
    if not s['asset_id'] or s['kind'] not in KINDS:
        sys.exit(f'slot needs asset_id and kind in {sorted(KINDS)}')
    only = set(a.only.split(',')) if a.only else set(ORDER)
    if only - set(ORDER):
        sys.exit(f'--only accepts {",".join(ORDER)}')
    if a.publish:
        try:
            ok = json.loads(Path(a.approval).read_text(encoding='utf-8')).get('asset_id') == s['asset_id']
        except (TypeError, OSError, ValueError, AttributeError):
            ok = False
        if not ok:
            sys.exit('BLOCKED: no GATE 2 approval for this asset, nothing was published')

    report = {'asset_id': s['asset_id'], 'kind': s['kind'], 'mode': 'publish' if a.publish else 'dry_run',
              'platforms': {}}
    plans = {}
    for k in ORDER:
        if k not in s['platforms']:
            continue
        if s['kind'] == 'story' and k != 'ig':  # TG/VK get stories via her own auto-repost
            report['platforms'][k] = {'status': 'skipped', 'reason': 'stories go to Instagram only'}
            continue
        if k not in only:
            report['platforms'][k] = {'status': 'skipped', 'reason': 'not in --only'}
            continue
        try:
            plans[k] = PLANNERS[k](s, s['platforms'][k])
        except Fail as e:
            report['platforms'][k] = {'status': 'invalid', 'error': str(e)}
    invalid = [k for k, v in report['platforms'].items() if v['status'] == 'invalid']
    if a.publish and invalid:  # publishing is all-or-nothing on validation
        report['blocked'] = f'validation failed for {",".join(invalid)}; nothing was published'
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    urls, host_err = {}, None
    need = hosting_needs(plans)
    if need:
        try:
            log(f'hosting {len(need)} file(s) in media/{s["asset_id"]}/ ...')
            urls = host(s['asset_id'], need)
        except (Fail, subprocess.CalledProcessError, OSError) as e:
            host_err = f'hosting failed: {e}'

    for k in ORDER:
        if k not in plans:
            continue
        log(f'{k}: {"publishing" if a.publish else "dry run"} ...')
        try:
            if k in ('ig', 'threads') and host_err:
                raise Fail(host_err)
            if k == 'ig':
                r = run_ig(plans[k], urls, a.publish)
            elif k == 'threads':
                r = run_threads(plans[k], urls, a.publish)
            elif k == 'vk':
                r = run_vk(plans[k], a.publish)
            else:
                r = run_tg(plans[k], a.publish)
            r['status'] = 'published' if a.publish else 'dry_run_ok'
        except (Fail, requests.RequestException, KeyError, ValueError, OSError) as e:
            r = {'status': 'error', 'error': redact(f'{type(e).__name__}: {e}')}
        report['platforms'][k] = r
    report['platforms'] = {k: report['platforms'][k] for k in ORDER if k in report['platforms']}
    if urls:
        report['hosted'] = sorted(urls.values())
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    sys.exit(1 if any(v['status'] in ('error', 'invalid') for v in report['platforms'].values()) else 0)


if __name__ == '__main__':
    main()
