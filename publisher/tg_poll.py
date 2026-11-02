#!/usr/bin/env python3
"""Send a poll to the Telegram channel. Usage: tg_poll.py POLL.json [--publish --approval FILE]
POLL.json: {"question": "...", "options": ["...", ...]}. Without --publish prints what it would send.
TELEGRAM_BOT_TOKEN comes from the environment; it is never printed."""
import argparse, json, os, sys
import requests
TG_API = 'https://api.telegram.org'
TG_CHAT = '-1002550616198'
ap = argparse.ArgumentParser(); ap.add_argument('poll'); ap.add_argument('--publish', action='store_true'); ap.add_argument('--approval')
a = ap.parse_args()
p = json.load(open(a.poll, encoding='utf-8'))
assert 2 <= len(p['options']) <= 10 and len(p['question']) <= 300
if not a.publish:
    print(json.dumps({'mode': 'dry_run', **p}, ensure_ascii=False, indent=1)); sys.exit(0)
if not a.approval or not os.path.exists(a.approval):
    sys.exit('approval file required')
tok = os.environ['TELEGRAM_BOT_TOKEN']
r = requests.post(f'{TG_API}/bot{tok}/sendPoll', data={'chat_id': TG_CHAT, 'question': p['question'],
    'options': json.dumps([{'text': o} for o in p['options']], ensure_ascii=False), 'is_anonymous': 'true'}, timeout=60)
j = r.json()
print(json.dumps({'ok': j.get('ok'), 'message_id': (j.get('result') or {}).get('message_id'), 'error': j.get('description')}, ensure_ascii=False))
sys.exit(0 if j.get('ok') else 1)
