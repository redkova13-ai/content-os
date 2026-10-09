"""Post-render check: every slide with a photo must show a whole face.
Usage: python3 check_faces.py spec.json out_dir   (exit 1 if any slide fails)"""
import json, os, sys
import cv2

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
    print(f'slide {i:02d} {s["photo"]}: {"OK" if ok else "NO FACE"}')
    if not ok:
        bad.append(i)
sys.exit(1 if bad else 0)
