"""Source of the HadaraLab logo SVGs (run: python assets/brand/make_logo.py).

The mark, in a 100x100 box: a Mesopotamian arch with a stepped (ziggurat) crown, and a
second-order step response inside it - it rises, overshoots once, then settles.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)

ARCH = ("M 8 88 V 50 A 24 26 0 0 1 32 24 V 17 H 41 V 9 H 59 V 17 H 68 V 24 "
        "A 24 26 0 0 1 92 50 V 88")
CURVE = "M 16 85 H 20 C 27 85 30 41 39 41 C 46 41 50 61 61 61 H 83"
INDIGO, TEAL = "#1F388C", "#2E8C80"


def mark(stroke, sw):
    return (f'<path d="{ARCH}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="miter"/>\n'
            f'    <path d="{CURVE}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')


def tile(sw, scale):
    """Rounded app tile with the white mark (scale < 1 leaves padding)."""
    tx, ty = 50 - 50 * scale, 51 - 48.5 * scale
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{TEAL}"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="96" height="96" rx="20" fill="url(#g)"/>
  <g transform="translate({tx:.2f} {ty:.2f}) scale({scale})">
    {mark("#FFFFFF", sw)}
  </g>
</svg>
'''


def mark_only(sw=7.2):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="4" y1="10" x2="96" y2="90">
      <stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{TEAL}"/>
    </linearGradient>
  </defs>
  <g transform="translate(0 2)">
    {mark("url(#g)", sw)}
  </g>
</svg>
'''


def write(name, text):
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as fh:
        fh.write(text)


write("app_icon.svg", tile(7.6, 0.74))           # large sizes (48 px and up)
write("app_icon_small.svg", tile(10.5, 0.78))    # 16-32 px: thicker lines stay readable
write("brand/logo_mark.svg", mark_only())
print("logo SVGs written")
