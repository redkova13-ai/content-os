#!/usr/bin/env python3
"""Publish a rendered carousel to Instagram (@irg_psy) via the Graph API.

Steps: PNG slides -> JPEG -> pushed to the public repo (raw.githubusercontent.com is the
image host Instagram pulls from) -> carousel item containers -> carousel container.
Without --publish it stops there (a dry run: Instagram checks every image, nothing is posted).
--publish needs an approval file written at GATE 2, so nothing goes out without Тата's ok.

The Graph API token is injected by the network proxy; it is never passed here.

usage: publish_carousel.py SLIDES_DIR --id ASSET_ID --caption CAPTION.txt [--publish --approval APPROVED.json]
"""
import argparse, json, os, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image

GRAPH = 'https://graph.facebook.com/v21.0'
IG_USER = '17841402153358869'  # @irg_psy
REPO = Path(__file__).resolve().parent.parent
RAW = 'https://raw.githubusercontent.com/redkova13-ai/content-os/main/'


def api(method, path, **params):
    data = urllib.parse.urlencode(params).encode() if method == 'POST' else None
    url = f'{GRAPH}/{path}' + ('' if method == 'POST' else '?' + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'Graph API error {e.code}: {e.read().decode()[:500]}')


def wait_ready(cid, tries=30):
    for _ in range(tries):
        st = api('GET', cid, fields='status_code,status')
        if st.get('status_code') == 'FINISHED':
            return
        if st.get('status_code') in ('ERROR', 'EXPIRED'):
            sys.exit(f'container {cid}: {st}')
        time.sleep(3)
    sys.exit(f'container {cid} not ready in time')


def host_images(slides_dir, asset_id):
    pngs = sorted(Path(slides_dir).glob('slide_*.png'))
    if not 2 <= len(pngs) <= 10:
        sys.exit(f'Instagram carousel needs 2–10 slides, found {len(pngs)}')
    dest = REPO / 'media' / asset_id
    dest.mkdir(parents=True, exist_ok=True)
    for p in pngs:  # Instagram accepts JPEG only
        Image.open(p).convert('RGB').save(dest / (p.stem + '.jpg'), quality=92, optimize=True)
    git = ['git', '-C', str(REPO), '-c', 'user.name=redkova13-ai', '-c', 'user.email=redkova13-ai@users.noreply.github.com']
    subprocess.run(git + ['add', str(dest)], check=True)
    if subprocess.run(git + ['diff', '--cached', '--quiet']).returncode:
        subprocess.run(git + ['commit', '-qm', f'media: {asset_id}'], check=True)
        subprocess.run(git + ['push', '-q', 'origin', 'HEAD:main'], check=True)
    urls = [RAW + f'media/{asset_id}/{p.stem}.jpg' for p in pngs]
    for u in urls:  # raw CDN can lag a few seconds after push
        for _ in range(20):
            try:
                urllib.request.urlopen(urllib.request.Request(u, method='HEAD'), timeout=20)
                break
            except Exception:
                time.sleep(3)
        else:
            sys.exit(f'image not reachable: {u}')
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('slides_dir')
    ap.add_argument('--id', required=True, help='CONTENT ASSET ID, used as the media folder name')
    ap.add_argument('--caption', required=True, help='text file with the post caption')
    ap.add_argument('--publish', action='store_true', help='actually post (needs --approval)')
    ap.add_argument('--approval', help='GATE 2 approval JSON: {"asset_id":..., "approved_by":..., "approved_at":...}')
    a = ap.parse_args()

    caption = Path(a.caption).read_text(encoding='utf-8').strip()
    if len(caption) > 2200:
        sys.exit(f'caption is {len(caption)} chars, Instagram limit is 2200')
    if a.publish:
        ok = a.approval and Path(a.approval).exists() and json.loads(Path(a.approval).read_text()).get('asset_id') == a.id
        if not ok:
            sys.exit('BLOCKED: no GATE 2 approval for this asset, nothing was published')

    urls = host_images(a.slides_dir, a.id)
    children = []
    for u in urls:
        c = api('POST', f'{IG_USER}/media', image_url=u, is_carousel_item='true')['id']
        children.append(c)
    for c in children:
        wait_ready(c)
    carousel = api('POST', f'{IG_USER}/media', media_type='CAROUSEL', children=','.join(children), caption=caption)['id']
    wait_ready(carousel)
    result = {'asset_id': a.id, 'slides': len(urls), 'container': carousel, 'published': False}

    if a.publish:
        media = api('POST', f'{IG_USER}/media_publish', creation_id=carousel)['id']
        info = api('GET', media, fields='permalink,timestamp')
        result.update(published=True, media_id=media, permalink=info.get('permalink'), timestamp=info.get('timestamp'))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
