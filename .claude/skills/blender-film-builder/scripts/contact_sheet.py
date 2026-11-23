"""Stack test frames vertically so one image shows several moments of a shot.
Usage: python3 contact_sheet.py <out.png> <frame1.png> [frame2.png ...]"""
import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]
ims = [Image.open(f).convert('RGB') for f in files]
w = max(i.width for i in ims); sheet = Image.new('RGB', (w, sum(i.height for i in ims)))
y = 0
for im in ims:
    sheet.paste(im, (0, y)); y += im.height
sheet.save(out); print(out)
