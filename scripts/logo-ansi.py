#!/usr/bin/env python3
"""Convertit un PNG RGBA en art ANSI truecolor (demi-blocs), bords adoucis sur le fond donné.
Usage : logo-ansi.py image.png LARGEUR [#fond] > logo.ansi"""
import sys, subprocess
src, w = sys.argv[1], int(sys.argv[2])
bg = sys.argv[3] if len(sys.argv) > 3 else '#0E0E16'
B = tuple(int(bg[i:i+2], 16) for i in (1, 3, 5))
raw = subprocess.check_output(['magick', src, '-resize', f'{w}x{w}', '-depth', '8', 'RGBA:-'])
h = len(raw) // 4 // w
px = [tuple(raw[i:i+4]) for i in range(0, len(raw), 4)]
def P(x, y):
    if y >= h: return None
    r, g, b, a = px[y*w + x]
    if a < 40: return None
    k = a / 255
    return tuple(round(c*k + bc*(1-k)) for c, bc in zip((r, g, b), B))
lines = []
for y in range(0, h, 2):
    s = ''
    for x in range(w):
        t, d = P(x, y), P(x, y+1)
        if t and d: s += '\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀\x1b[0m' % (t + d)
        elif t:     s += '\x1b[38;2;%d;%d;%dm▀\x1b[0m' % t
        elif d:     s += '\x1b[38;2;%d;%d;%dm▄\x1b[0m' % d
        else:       s += ' '
    lines.append(s.rstrip())
while lines and not lines[-1]: lines.pop()
while lines and not lines[0]: lines.pop(0)
print('\n'.join(lines))
