"""Post-render check: every slide with a photo must show a whole face, and the face must be in the light
(Тата 2.11.2026: covers have dark gradients, a face half in shadow looks «наполовину демон, наполовину ангел»).
Light = median L* of the inner face: <35 fails («В ТЕНИ»), <40 or a strong light/shadow split warns («СВЕТ?», check by eye).
A slide with "scene": true (generated people, not Татьяна) is not light-checked.
Usage: python3 check_faces.py spec.json out_dir   (exit 1 if any slide fails)"""
import json, os, sys
import cv2
import numpy as np

spec, out = sys.argv[1], sys.argv[2]
slides = json.load(open(spec))['slides']
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'yunet.onnx')

def faces(img):
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(MODEL, '', (w, h), 0.7)
    _, found = det.detect(img)
    return [] if found is None else [tuple(int(v) for v in f[:4]) for f in found]

bad = []
for i, s in enumerate(slides, 1):
    if not s.get('photo'):
        continue
    img = cv2.imread(os.path.join(out, f'slide_{i:02d}.png'))
    h, w = img.shape[:2]
    m = 8  # px margin: a face touching the slide edge counts as cut
    ok = [f for f in faces(img) if f[0] > m and f[1] > m and f[0] + f[2] < w - m and f[1] + f[3] < h - m]
    if not ok:
        print(f'slide {i:02d} {s["photo"]}: NO FACE')
        bad.append(i)
        continue
    x, y, fw, fh = max(ok, key=lambda f: f[2] * f[3])
    inner = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[y + fh // 5:y + fh, x + fw // 6:x + fw - fw // 6, 0].astype(float) * 100 / 255
    p25, med, p75 = np.percentile(inner, [25, 50, 75])
    light = f'light {med:.0f} (spread {p75 - p25:.0f})'
    if s.get('scene'):
        print(f'slide {i:02d} {s["photo"]}: OK, scene, {light}')
    elif med < 35:
        print(f'slide {i:02d} {s["photo"]}: В ТЕНИ, {light}: lighten the face (lighter photo, gradient away from the face, focus/_padL) or change photo')
        bad.append(i)
    elif med < 40 or p75 - p25 > 30:
        print(f'slide {i:02d} {s["photo"]}: СВЕТ?, {light}: look by eye, half the face must not sink into shadow')
    else:
        print(f'slide {i:02d} {s["photo"]}: OK, {light}')
sys.exit(1 if bad else 0)
