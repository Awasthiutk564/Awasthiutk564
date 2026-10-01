"""
Prepare a portrait photo for clean ASCII conversion:
  1. remove the background (rembg) so the subject is isolated
  2. boost LOCAL contrast (CLAHE) so a flatly-lit face gains highlights and
     shadows -- this is what turns a dark blob into a recognizable face
  3. composite the subject onto pure white so the background reads as blank
     (white -> spaces in the ascii ramp)

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
Run once whenever the source photo changes; the ascii SVG itself is static.

    python scripts/prep_photo.py <input.jpg> [output.png]
"""
import glob
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def default_input():
    found = sorted(glob.glob(os.path.join(ROOT, "source-photo.*")))
    if not found:
        sys.exit("no source-photo.* found in the repo root")
    return found[0]


INP = sys.argv[1] if len(sys.argv) > 1 else default_input()
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "source-prepped.png")

# head-and-shoulders crop: keep a square this fraction of the subject's height,
# starting at the top of the head and centered on it. a half-body photo leaves
# the face tiny in a 100-column grid; set to 1.0 for an already tight headshot.
BUST = 0.55

# 1. cut out the subject (exif_transpose so phone photos aren't sideways)
cut = remove(ImageOps.exif_transpose(Image.open(INP)).convert("RGBA"))
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])                 # 0 = background

# crop to the subject so the face fills the frame
ys, xs = np.where(alpha > 16)
if len(xs):
    pad = 12
    y0, y1 = max(0, ys.min() - pad), min(alpha.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(alpha.shape[1], xs.max() + pad)
    rgb, alpha = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]

# 2. local-contrast the luminance (CLAHE)
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8))
gray = clahe.apply(gray)

# a touch of global lift so the face sits in the sparse end of the ramp
gray = cv2.convertScaleAbs(gray, alpha=1.05, beta=18)

# 3. paste onto white using the alpha mask (feathered a hair to avoid a halo)
mask = alpha.astype(np.float32) / 255.0
mask = cv2.GaussianBlur(mask, (0, 0), 1.0)
out = gray.astype(np.float32) * mask + 255.0 * (1.0 - mask)
out = np.clip(out, 0, 255).astype(np.uint8)

# 4. crop to head and shoulders, centered on the head
h, w = out.shape
if BUST < 1.0:
    side = int(h * BUST)
    head = out[: int(h * 0.25)]
    cols = np.where((head < 200).any(axis=0))[0]
    cx = (cols.min() + cols.max()) // 2 if len(cols) else w // 2
    x0 = max(0, min(w - side, cx - side // 2))
    out = out[:side, x0:x0 + side]

# square it up on white so the portrait is centered in the ascii grid
h, w = out.shape
side = max(h, w)
canvas = np.full((side, side), 255, np.uint8)
canvas[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = out

Image.fromarray(canvas, mode="L").save(OUT)
print("wrote", OUT, canvas.shape)
