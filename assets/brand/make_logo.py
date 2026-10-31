"""Build the HadaraLab icon files from the designer's artwork (run: python assets/brand/make_logo.py).

Icon and visual identity by Ahmed Al Basri (instagram.com/dcssi_, github.com/ahmedalbasr).
The source files in assets/brand/source are his exports, used as they are:

    icon_blue.png    1024 x 1024 app icon: navy background, blue column
    glyph_white.png  the white column on a transparent background
    glyph_blue.png   the blue column on a transparent background

The app icon is the designer's background with the white column placed exactly where
his blue column is. Brand colors: navy #020A21, blue #528CF1, mint #7DD3B0.
"""
import os

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)
SRC = os.path.join(HERE, "source")
NAVY = (2, 10, 33)
GLYPH_BOX = (328, 278, 697, 747)      # the blue column in icon_blue.png (left, top, right, bottom)

bg = Image.open(os.path.join(SRC, "icon_blue.png")).convert("RGBA")
glyph = Image.open(os.path.join(SRC, "glyph_white.png")).convert("RGBA")

# take the blue column out of the background: anything that is not navy around it becomes navy
mask = Image.new("L", bg.size, 0)
px, mp = bg.load(), mask.load()
l, t, r, b = GLYPH_BOX
for y in range(t - 6, b + 6):
    for x in range(l - 6, r + 6):
        if sum(abs(c - n) for c, n in zip(px[x, y][:3], NAVY)) > 12:
            mp[x, y] = 255
mask = mask.filter(ImageFilter.MaxFilter(5))        # cover the anti-aliased edge too
bg.paste(Image.new("RGBA", bg.size, NAVY + (255,)), (0, 0), mask)

# the white column, same place and size as the blue one
w, h = r - l, b - t
icon = bg.copy()
icon.alpha_composite(glyph.resize((w, h), Image.LANCZOS), (l, t))

icon.save(os.path.join(HERE, "app_icon_1024.png"))
icon.resize((256, 256), Image.LANCZOS).save(os.path.join(ASSETS, "app_icon_256.png"))
sizes = [256, 128, 64, 48, 40, 32, 24, 20, 16]
icon.resize((256, 256), Image.LANCZOS).save(
    os.path.join(ASSETS, "app_icon.ico"), format="ICO", sizes=[(s, s) for s in sizes])

# the white column alone, for the navy header and the splash screen
mark = glyph.copy()
mark.thumbnail((512, 512), Image.LANCZOS)
mark.save(os.path.join(HERE, "logo_mark_white.png"))

# the white column as the small icon of the window title bar (next to minimise / close)
square = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
col = glyph.copy()
col.thumbnail((256, 256), Image.LANCZOS)
square.alpha_composite(col, ((256 - col.width) // 2, (256 - col.height) // 2))
square.save(os.path.join(HERE, "titlebar_icon.ico"), format="ICO",
            sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64)])

# the blue column alone, next to the name on the start page
blue = Image.open(os.path.join(SRC, "glyph_blue.png")).convert("RGBA")
blue.thumbnail((512, 512), Image.LANCZOS)
blue.save(os.path.join(HERE, "logo_mark_blue.png"))
print("icons written")
