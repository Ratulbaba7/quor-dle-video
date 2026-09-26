"""Quordle thumbnail generator (1280x720), self-contained (Pillow only).

2026 redesign matching the Wordle channel thumbnail quality:
  - Kicker badge with exact search phrase "QUORDLE ANSWER TODAY"
  - Huge "ALL 6 MODES SOLVED" headline
  - 4 mini boards with curiosity-gap tiles (first letters revealed)
  - Per-mode answer chips (Classic answers shown)
  - Puzzle date on green card + full date banner
  - Bold outlined text + Wordle-green/yellow palette for CTR
"""
import os
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.LANCZOS
except Exception:
    Image = ImageDraw = ImageFont = None

GREEN = (46, 204, 113)
GREEN_DARK = (28, 150, 82)
YELLOW = (255, 205, 0)
BG_TOP = (13, 20, 38)
BG_BOT = (30, 45, 80)
WHITE = (255, 255, 255)
OUTLINE = (8, 12, 22)
GRAY = (110, 118, 132)
DARK = (15, 23, 42)


def _load_thumbnail_fonts():
    """Load bold display fonts across platforms (Linux CI + Windows dev)."""
    candidates = [
        ("C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", None),
    ]
    for display_path, fallback_path in candidates:
        try:
            if os.path.exists(display_path):
                return {
                    'display': ImageFont.truetype(display_path, 110),
                    'title': ImageFont.truetype(display_path, 84),
                    'number': ImageFont.truetype(display_path, 100),
                    'badge': ImageFont.truetype(fallback_path or display_path, 36),
                    'tile': ImageFont.truetype(display_path, 56),
                    'chip': ImageFont.truetype(fallback_path or display_path, 32),
                }
        except Exception:
            continue
    default = ImageFont.load_default()
    return {k: default for k in
            ('display', 'title', 'number', 'badge', 'tile', 'chip')}


def generate_quordle_thumbnail(out_path, date_str, official_map=None, mode_count=6):
    """Render a 1280x720 Quordle thumbnail. Returns True on success."""
    if Image is None:
        print("[thumbnail] Pillow unavailable; skipping")
        return False
    try:
        W, H = 1280, 720
        img = Image.new("RGB", (W, H), BG_TOP)
        d = ImageDraw.Draw(img)

        # Vertical gradient background
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)],
                   fill=(int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
                         int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
                         int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)))

        fonts = _load_thumbnail_fonts()

        def shadow(pos, txt, fill, font, anchor=None, off=5, stroke=3):
            x, y = pos
            d.text((x + off, y + off), txt, fill=OUTLINE, font=font, anchor=anchor)
            d.text(pos, txt, fill=fill, font=font, anchor=anchor,
                   stroke_width=stroke, stroke_fill=OUTLINE)

        # ---- Right side: big date card -------------------------------
        # Parse "September 25, 2026" -> "SEP 25" big + "2026" small
        try:
            _dt = datetime.strptime(date_str, "%B %d, %Y")
            short_date = _dt.strftime("%b %d").upper()
            year = str(_dt.year)
        except Exception:
            short_date = date_str.upper()
            year = ""

        card_w, card_h = 350, 280
        card_x, card_y = W - card_w - 50, 50
        d.rounded_rectangle(
            [card_x + 10, card_y + 12, card_x + card_w + 10, card_y + card_h + 12],
            radius=36, fill=(8, 12, 22))  # drop shadow
        d.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=36, fill=GREEN, outline=WHITE, width=6)
        d.text((card_x + card_w // 2, card_y + 50), "DAILY PUZZLE",
               fill=(220, 255, 235), font=fonts['badge'], anchor="mm")
        shadow((card_x + card_w // 2, card_y + 150),
               short_date, fill=WHITE, font=fonts['number'], anchor="mm")
        if year:
            d.text((card_x + card_w // 2, card_y + 215),
                   year, fill=(220, 255, 235), font=fonts['badge'], anchor="mm")
        # Mini grid motif
        mini, mgap = 28, 8
        total_mini = 5 * mini + 4 * mgap
        mx = card_x + (card_w - total_mini) // 2
        my = card_y + card_h - 56
        for i in range(5):
            c = GREEN_DARK if i < 2 else (255, 255, 255)
            d.rounded_rectangle(
                [mx + i * (mini + mgap), my,
                 mx + i * (mini + mgap) + mini, my + mini],
                radius=8, fill=c)

        # ---- Left side: kicker badge + headline -----------------------
        kick_txt = "QUORDLE ANSWER TODAY"
        kb = fonts['badge']
        kb_box = d.textbbox((0, 0), kick_txt, font=kb)
        kw, kh = kb_box[2] - kb_box[0], kb_box[3] - kb_box[1]
        kx, ky = 50, 60
        d.rounded_rectangle([kx - 22, ky - 16, kx + kw + 22, ky + kh + 26],
                            radius=14, fill=YELLOW)
        d.text((kx, ky - 4), kick_txt, fill=(15, 15, 15), font=kb)

        shadow((46, 125), "TODAY'S", WHITE, fonts['display'])
        shadow((46, 235), "QUORDLE", GREEN, fonts['display'])
        shadow((46, 345), "ALL 6 MODES SOLVED!", YELLOW, fonts['title'])

        # ---- 4 mini boards with curiosity-gap tiles -------------------
        answers = (official_map or {}).get("Classic") or []
        bx, by, tile, gap = 44, 430, 52, 10
        board_gap = 36
        for b in range(4):
            ox = bx + b * (5 * tile + 4 * gap + board_gap)
            if ox + 5 * tile + 4 * gap > W - 44:
                break
            for r in range(2):
                for c in range(5):
                    x = ox + c * (tile + gap)
                    y = by + r * (tile + gap)
                    if r == 0 and c < 2:
                        col = GREEN
                    elif r == 0 and c == 2:
                        col = YELLOW
                    else:
                        col = GRAY
                    d.rounded_rectangle([x, y, x + tile, y + tile],
                                        radius=8, fill=col, outline=WHITE, width=2)
                    # Reveal first letter of first row (curiosity gap)
                    if r == 0 and c < 2 and answers and b < len(answers):
                        try:
                            _w = answers[b]
                            if len(_w) > c:
                                d.text((x + tile // 2, y + tile // 2),
                                       _w[c].upper(), fill=WHITE,
                                       font=fonts['tile'], anchor="mm",
                                       stroke_width=2, stroke_fill=OUTLINE)
                        except Exception:
                            pass
                    elif r == 0 and c == 2:
                        d.text((x + tile // 2, y + tile // 2),
                               "?", fill=(15, 15, 15),
                               font=fonts['tile'], anchor="mm")

        # ---- Answer chips (Classic answers if available) ---------------
        if answers:
            cx = 44
            for w in answers[:4]:
                _bbox = d.textbbox((0, 0), w, font=fonts['chip'])
                tw = _bbox[2] - _bbox[0] + 56
                if cx + tw > W - 50:
                    break
                d.rounded_rectangle([cx, 570, cx + tw, 570 + 62], radius=12,
                                    fill=DARK, outline=GREEN, width=3)
                d.text((cx + tw // 2, 601), w, fill=WHITE,
                       font=fonts['chip'], anchor="mm")
                cx += tw + 14

        # ---- Date banner (FULL date incl. year) -----------------------
        if date_str:
            d_txt = date_str.upper()
            db = d.textbbox((0, 0), d_txt, font=fonts['badge'])
            dw, dh = db[2] - db[0], db[3] - db[1]
            dx, dy = 44, H - dh - 52
            d.rounded_rectangle([dx - 18, dy - 14, dx + dw + 18, dy + dh + 22],
                                radius=14, fill=DARK, outline=YELLOW, width=4)
            d.text((dx, dy - 2), d_txt, fill=YELLOW, font=fonts['badge'])

        # ---- CTA bottom-right ------------------------------------------
        cta_txt = "ALL ANSWERS + TIPS >>"
        cb = d.textbbox((0, 0), cta_txt, font=fonts['badge'])
        cw, ch = cb[2] - cb[0], cb[3] - cb[1]
        cx, cy = W - cw - 75, H - ch - 52
        d.rounded_rectangle([cx - 18, cy - 14, cx + cw + 18, cy + ch + 22],
                            radius=14, fill=GREEN)
        d.text((cx, cy - 2), cta_txt, fill=(15, 15, 15), font=fonts['badge'])

        img.save(out_path, "PNG", optimize=True)
        print(f"[thumbnail] Saved to {out_path}")
        return True
    except Exception as e:
        print(f"[thumbnail] failed: {e}")
        return False


if __name__ == "__main__":
    generate_quordle_thumbnail("_thumb_test.png",
                               datetime.now().strftime("%B %d, %Y"),
                               {"Classic": ["SWEAR", "FLOOD", "GUPPY", "GROAN"]})
