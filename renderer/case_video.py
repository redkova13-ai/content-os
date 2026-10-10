"""Сборка кейсового Reels: сцены-картинки с медленным наездом, субтитры, плашка.

python3 case_video.py SPEC.json OUT.mp4
SPEC: {"scenes_dir": ..., "note": "...", "audio": optional path,
       "scenes": [{"img": "s1.png", "text": "...", "start": opt sec, "end": opt sec}]}
Без audio длительность сцены считается по длине текста (черновик для просмотра).
"""
import json, os, re, subprocess, sys, tempfile

W, H, FPS, CPS, XF = 1080, 1920, 30, 15.0, 0.5

def chunks(text, maxlen=34, lines=2):
    words, cur, out = text.split(), '', []
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxlen:
            out.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur: out.append(cur)
    return ['\\N'.join(out[i:i + lines]) for i in range(0, len(out), lines)]

def ts(t):
    h, t = divmod(t, 3600); m, s = divmod(t, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"

def main(spec_path, out):
    spec = json.load(open(spec_path))
    sc = spec['scenes']
    if not all('start' in s for s in sc):
        t = 0.0
        for s in sc:
            d = max(4.0, len(s['text']) / CPS)
            s['start'], s['end'] = t, t + d; t += d
    total = sc[-1]['end']
    tmp = tempfile.mkdtemp()
    ass = os.path.join(tmp, 'subs.ass')
    ev = []
    for s in sc:
        cs = chunks(s['text']); dur = (s['end'] - s['start']) / len(cs)
        weights = [len(c) for c in cs]; tot = sum(weights); t = s['start']
        for c, w in zip(cs, weights):
            d = (s['end'] - s['start']) * w / tot
            ev.append(f"Dialogue: 0,{ts(t)},{ts(t + d - 0.05)},Sub,,0,0,0,,{c}"); t += d
    note = spec.get('note')
    if note:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(total)},Note,,0,0,0,,{note}")
    open(ass, 'w').write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter SemiBold,58,&H00FFFFFF,&H00FFFFFF,&H00201814,&H96000000,0,0,0,0,100,100,0,0,1,4,2,2,90,90,520,1
Style: Note,Inter,30,&H00A8C9E9,&H00FFFFFF,&H00201814,&H64000000,0,0,0,0,100,100,0,0,1,2,1,8,80,80,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + '\n'.join(ev) + '\n')
    inputs, fl = [], []
    for i, s in enumerate(sc):
        d = s['end'] - s['start'] + (XF if i < len(sc) - 1 else 0)
        n = int(d * FPS)
        inputs += ['-loop', '1', '-t', f'{d:.3f}', '-i', os.path.join(spec['scenes_dir'], s['img'])]
        z = "1.0+0.12*on/%d" % n if i % 2 == 0 else "1.12-0.12*on/%d" % n
        fl.append(f"[{i}:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},setsar=1[v{i}]")
    last, off = 'v0', 0.0
    for i in range(1, len(sc)):
        off += sc[i - 1]['end'] - sc[i - 1]['start']
        fl.append(f"[{last}][v{i}]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]"); last = f'x{i}'
    fl.append(f"[{last}]ass={ass},format=yuv420p[out]")
    cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inputs
    if spec.get('audio'):
        cmd += ['-i', spec['audio']]; amap = ['-map', f'{len(sc)}:a', '-c:a', 'aac', '-b:a', '160k']
    else:
        cmd += ['-f', 'lavfi', '-t', f'{total:.3f}', '-i', 'anullsrc=r=44100:cl=stereo']; amap = ['-map', f'{len(sc)}:a', '-c:a', 'aac']
    cmd += ['-filter_complex', ';'.join(fl), '-map', '[out]'] + amap + \
           ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-r', str(FPS), '-t', f'{total:.3f}', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    print(f'ok {out} {total:.1f}s')

if __name__ == '__main__':
    main(*sys.argv[1:3])
