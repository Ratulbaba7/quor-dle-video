"""Quordle thumbnail generator (1280x720), self-contained (Pillow only).
Added to the quor-dle-video project. Produces a 4-board themed card with the
date + "QUORDLE ANSWER TODAY" kicker + per-mode answer chips.
"""
import os
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.LANCZOS
except Exception:
    Image = ImageDraw = ImageFont = None

GREEN = (0, 204, 136)
YELLOW = (255, 205, 0)
BG_TOP = (13, 20, 38)
BG_BOT = (30, 45, 80)
WHITE = (255, 255, 255)
OUTLINE = (8, 12, 22)
GRAY = (110, 118, 132)


def _font(size, bold=True, italic=False):
    cands = []
    if italic:
        cands += ["C:/Windows/Fonts/segoeuiz.ttf"]
    if bold:
        cands += ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                  "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/impact.ttf"]
    else:
        cands += ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
              if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for c in cands:
        if c and os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_quordle_thumbnail(out_path, date_str, official_map=None, mode_count=6):
    """Render a 1280x720 Quordle thumbnail. Returns True on success."""
    if Image is None:
        print("[thumbnail] Pillow unavailable; skipping")
        return False
    try:
        W, H = 1280, 720
        img = Image.new("RGB", (W, H), BG_TOP)
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)],
                   fill=(int(BG_TOP[0] + (BG_BOT[0]-BG_TOP[0])*t),
                         int(BG_TOP[1] + (BG_BOT[1]-BG_TOP[1])*t),
                         int(BG_TOP[2] + (BG_BOT[2]-BG_TOP[2])*t)))

        def shadow(pos, txt, fill, font, anchor=None, off=5):
            x, y = pos
            d.text((x+off, y+off), txt, fill=OUTLINE, font=font, anchor=anchor)
            d.text(pos, txt, fill=fill, font=font, anchor=anchor,
                   stroke_width=3, stroke_fill=OUTLINE)

        # Kicker badge
        d.rounded_rectangle([40, 44, 40 + 560, 44 + 78], radius=14, fill=YELLOW)
        d.text((70, 62), "QUORDLE ANSWER TODAY", fill=(15, 15, 15), font=_font(44))

        # Big title
        shadow((44, 150), "TODAY'S QUORDLE", WHITE, _font(78))
        shadow((44, 245), "ALL 6 MODES SOLVED", GREEN, _font(52))

        # 4 mini boards motif
        bx, by, tile, gap = 46, 340, 62, 12
        for b in range(4):
            ox = bx + b * (5*tile + 4*gap + 40)
            for r in range(2):
                for c in range(5):
                    x = ox + c*(tile+gap); y = by + r*(tile+gap)
                    if r == 1:
                        col = GREEN if c < 3 else GRAY
                    else:
                        col = GRAY
                    d.rounded_rectangle([x, y, x+tile, y+tile], radius=8, fill=col)

        # Answer chips (Classic mode answers if available)
        answers = (official_map or {}).get("Classic") or []
        if answers:
            cx = 46
            for w in answers[:4]:
                tw = 190
                d.rounded_rectangle([cx, 520, cx+tw, 520+66], radius=12,
                                    fill=(20, 30, 55), outline=GREEN, width=3)
                d.text((cx+tw//2, 553), w, fill=WHITE, font=_font(38), anchor="mm")
                cx += tw + 16

        # Date + modes
        d.text((46, 620), date_str.upper(), fill=YELLOW, font=_font(40))
        d.text((W-46, 628), "CLASSIC • CHILL • EXTREME • SEQUENCE • RESCUE • WEEKLY",
               fill=(180, 190, 210), font=_font(22), anchor="ra")

        img.save(out_path, "PNG", optimize=True)
        print(f"[thumbnail] {out_path}")
        return True
    except Exception as e:
        print(f"[thumbnail] failed: {e}")
        return False


if __name__ == "__main__":
    generate_quordle_thumbnail("_thumb_test.png", datetime.now().strftime("%B %d, %Y"),
                               {"Classic": ["SWEAR", "FLOOD", "GUPPY", "GROAN"]})
