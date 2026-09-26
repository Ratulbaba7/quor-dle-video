"""Quordle parity helpers — Wordle-level features for quordle-video.

Covers: hints, analysis slides (definition/frequency/facts), recap/teaser,
SEO title/tags, captions SRT, playlist/pin/thumbnail helpers,
uniform full-video music, fake-JS-date init script (time-travel trick).
Pillow-only for images; moviepy optional for assembly (ffmpeg fallback).
"""
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = ImageDraw = ImageFont = None

SLIDE_W, SLIDE_H = 1920, 1080
BG_TOP = (13, 20, 38)
BG_BOT = (30, 45, 80)
CARD = (23, 34, 58)
CARD_BORDER = (52, 68, 100)
TEXT = (255, 255, 255)
MUTED = (168, 180, 200)
GREEN = (46, 204, 113)
YELLOW = (255, 205, 0)
GRAY = (110, 118, 132)

SCRABBLE_SCORES = {
    'a': 1, 'b': 3, 'c': 3, 'd': 2, 'e': 1, 'f': 4, 'g': 2, 'h': 4,
    'i': 1, 'j': 8, 'k': 5, 'l': 1, 'm': 3, 'n': 1, 'o': 1, 'p': 3,
    'q': 10, 'r': 1, 's': 1, 't': 1, 'u': 1, 'v': 4, 'w': 4, 'x': 8,
    'y': 4, 'z': 10,
}

ENGLISH_FREQ = {
    'e': (12.7, 1), 't': (9.1, 2), 'a': (8.2, 3), 'o': (7.5, 4),
    'i': (7.0, 5), 'n': (6.7, 6), 's': (6.3, 7), 'h': (6.1, 8),
    'r': (6.0, 9), 'd': (4.3, 10), 'l': (4.0, 11), 'c': (2.8, 12),
    'u': (2.8, 13), 'm': (2.4, 14), 'w': (2.4, 15), 'f': (2.2, 16),
    'g': (2.0, 17), 'y': (2.0, 18), 'p': (1.9, 19), 'b': (1.5, 20),
    'v': (1.0, 21), 'k': (0.8, 22), 'j': (0.15, 23), 'x': (0.15, 24),
    'q': (0.10, 25), 'z': (0.07, 26),
}


def format_chapter_timestamp(seconds):
    try:
        total = max(0, int(round(seconds)))
        return f"{total // 60}:{total % 60:02d}"
    except Exception:
        return "0:00"


def compute_hints_for_word(solution):
    """3 progressive hints for one 5-letter word (Wordle parity)."""
    try:
        if not solution or len(solution) != 5:
            return []
        s = solution.upper()
        vowels = sum(1 for c in s if c in "AEIOU")
        unique = len(set(s))
        return [
            f"Hint 1: {vowels} vowel(s)",
            f"Hint 2: Starts with '{s[0]}'",
            f"Hint 3: {'All unique' if unique == 5 else f'{5-unique} repeat'}",
        ]
    except Exception:
        return []


def _load_fonts():
    pairs = [
        ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeui.ttf"),
        ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_path = regular_path = None
    for b, r in pairs:
        if os.path.exists(b):
            bold_path = b
            regular_path = r if (r and os.path.exists(r)) else b
            break
    if not bold_path or ImageFont is None:
        d = ImageFont.load_default() if ImageFont else None
        return {k: d for k in ('big', 'title', 'medium', 'bold', 'body', 'small', 'regular', 'tile')}
    return {
        'big': ImageFont.truetype(bold_path, 110),
        'tile': ImageFont.truetype(bold_path, 90),
        'title': ImageFont.truetype(bold_path, 70),
        'medium': ImageFont.truetype(bold_path, 50),
        'bold': ImageFont.truetype(bold_path, 40),
        'body': ImageFont.truetype(regular_path, 40),
        'small': ImageFont.truetype(regular_path, 30),
        'regular': ImageFont.truetype(regular_path, 36),
    }


def _slide_base(kicker, meta_text):
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(SLIDE_H):
        t = y / SLIDE_H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (SLIDE_W, y)], fill=(r, g, b))
    fonts = _load_fonts()
    draw.rectangle([0, 0, 14, SLIDE_H], fill=GREEN)
    draw.text((70, 52), kicker.upper(), fill=GREEN, font=fonts['medium'])
    if meta_text:
        try:
            mw = draw.textlength(meta_text, font=fonts['small'])
            draw.text((SLIDE_W - 70 - mw, 66), meta_text, fill=MUTED, font=fonts['small'])
        except Exception:
            pass
    return img, draw, fonts, 200


def generate_quordle_hints_image(out_path, date_str, classic_words):
    """4-column hints card: one 3-hint column per Classic answer."""
    if Image is None:
        return False
    try:
        W, H = 1920, 1080
        img = Image.new("RGB", (W, H), BG_TOP)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()
        draw.text((W // 2 - 450, 70), "HINTS — ALL 4 CLASSIC WORDS", fill=GREEN, font=fonts['title'])
        draw.text((W // 2 - 120, 160), date_str, fill=TEXT, font=fonts['small'])
        words = (classic_words or [])[:4]
        card_w, card_h = 420, 560
        gap = 40
        total_w = card_w * 4 + gap * 3
        start_x = (W - total_w) // 2
        card_y = 260
        for i, w in enumerate(words):
            x = start_x + i * (card_w + gap)
            draw.rectangle([x, card_y, x + card_w, card_y + card_h], fill=CARD)
            draw.text((x + 30, card_y + 20), f"WORD {i+1}", fill=YELLOW, font=fonts['bold'])
            draw.text((x + 30, card_y + 80), "XXXXX", fill=MUTED, font=fonts['medium'])
            hints = compute_hints_for_word(w)
            ty = card_y + 180
            for h in hints:
                draw.text((x + 30, ty), h[:28], fill=TEXT, font=fonts['body'])
                ty += 60
            # curiosity: reveal first letter
            if w:
                draw.text((x + 30, ty + 20), f"Starts: {w[0].upper()} _ _ _ _", fill=GREEN, font=fonts['bold'])
        draw.text((W // 2 - 350, H - 90), "Pause & guess before the solve!", fill=YELLOW, font=fonts['small'])
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"[quordle-hints] failed: {e}")
        return False


def get_letter_frequency_info(words):
    try:
        letters = sorted(set("".join(w.lower() for w in (words or []) if w)))
        if not letters:
            return {}
        avg = sum(ENGLISH_FREQ.get(c, (0, 0))[0] for c in letters) / len(letters)
        tier = "very common" if avg > 7.0 else ("common" if avg > 4.0 else ("moderately rare" if avg > 2.0 else "rare"))
        return {"letters": letters, "avg_freq": round(avg, 1), "tier": tier}
    except Exception:
        return {}


def generate_quordle_definition_slide(out_path, date_str, classic_words, analysis):
    if Image is None:
        return False
    try:
        img, draw, fonts, y = _slide_base("Quordle Analysis — Definitions", date_str)
        words = (classic_words or [])[:4]
        draw.text((70, y), "TODAY'S 4 ANSWERS", fill=TEXT, font=fonts['title'])
        y += 120
        for w in words:
            wu = (w or "").upper()
            a = (analysis or {}).get(wu, {})
            defn = a.get("definition", "") if isinstance(a, dict) else ""
            pos = a.get("part_of_speech", "") if isinstance(a, dict) else ""
            card_h = 150
            draw.rounded_rectangle([70, y, SLIDE_W - 70, y + card_h], radius=20, fill=CARD, outline=CARD_BORDER, width=2)
            chip = (pos or "word").upper()[:12]
            draw.rounded_rectangle([100, y + 24, 100 + 220, y + 82], radius=12, fill=GREEN)
            draw.text((132, y + 32), chip, fill=(10, 20, 14), font=fonts['bold'])
            draw.text((340, y + 32), wu, fill=TEXT, font=fonts['bold'])
            if defn:
                draw.text((100, y + 92), defn[:90], fill=TEXT, font=fonts['regular'])
            y += card_h + 20
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"[quordle-def] failed: {e}")
        return False


def generate_quordle_frequency_slide(out_path, date_str, classic_words, letter_freq):
    if Image is None:
        return False
    try:
        img, draw, fonts, y = _slide_base("Letter Frequency Analysis", date_str)
        draw.text((70, y), "How common are today's letters?", fill=TEXT, font=fonts['title'])
        y += 120
        letters = sorted(set("".join(w.lower() for w in (classic_words or []) if w)),
                         key=lambda c: -ENGLISH_FREQ.get(c, (0, 27))[0])[:8]
        max_freq = 12.7
        bar_max_w = SLIDE_W - 700
        for letter in letters:
            freq, rank = ENGLISH_FREQ.get(letter, (0.05, 27))
            draw.rounded_rectangle([70, y, 142, y + 72], radius=14, fill=GREEN if freq >= 4.0 else GRAY)
            draw.text((106, y + 36), letter.upper(), fill=(10, 20, 14), font=fonts['bold'], anchor="mm")
            bar_w = max(24, int(bar_max_w * (freq / max_freq)))
            draw.rounded_rectangle([170, y + 12, 170 + bar_max_w, y + 60], radius=10, fill=(30, 42, 66))
            draw.rounded_rectangle([170, y + 12, 170 + bar_w, y + 60], radius=10, fill=GREEN)
            draw.text((190 + bar_max_w, y + 36), f"{freq:.1f}%", fill=TEXT, font=fonts['bold'])
            draw.text((190 + bar_max_w + 150, y + 36), f"#{rank}", fill=MUTED, font=fonts['small'])
            y += 92
        tier = (letter_freq or {}).get("tier", "common")
        draw.text((70, SLIDE_H - 120), f"rarity: {tier} | {(len(letters))} unique letters", fill=YELLOW, font=fonts['bold'])
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"[quordle-freq] failed: {e}")
        return False


def generate_quordle_facts_slide(out_path, date_str, classic_words):
    if Image is None:
        return False
    try:
        img, draw, fonts, y = _slide_base("Quordle Facts & Solve Path", date_str)
        words = [w.lower() for w in (classic_words or []) if w]
        scrabble = sum(SCRABBLE_SCORES.get(c, 0) for w in words for c in w)
        vowels = sum(1 for w in words for c in w if c in "aeiou")
        facts = [
            ("WORDS", f"{len(words)} solved"),
            ("LETTERS", f"{len(words)*5} total"),
            ("VOWELS", f"{vowels}"),
            ("SCRABBLE", f"{scrabble} pts"),
            ("MODES", "6/6 solved"),
            ("STREAK", "keep it alive!"),
        ]
        cx, cy = 70, y + 40
        for k, v in facts:
            draw.rounded_rectangle([cx, cy, cx + 520, cy + 140], radius=16, fill=CARD, outline=CARD_BORDER, width=2)
            draw.text((cx + 24, cy + 16), k, fill=GREEN, font=fonts['bold'])
            draw.text((cx + 24, cy + 70), v, fill=TEXT, font=fonts['title'])
            cx += 560
            if cx + 520 > SLIDE_W - 70:
                cx = 70
                cy += 170
        # solve path chips: the 4 answers
        py = cy + 190
        draw.text((70, py), "SOLVE PATH:", fill=YELLOW, font=fonts['bold'])
        py += 70
        xx = 70
        for w in words:
            wu = w.upper()
            tw = 220
            draw.rounded_rectangle([xx, py, xx + tw, py + 70], radius=12, fill=CARD, outline=GREEN, width=3)
            draw.text((xx + tw // 2, py + 35), wu, fill=TEXT, font=fonts['bold'], anchor="mm")
            xx += tw + 20
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"[quordle-facts] failed: {e}")
        return False


def generate_quordle_recap_image(out_path, ytd_info):
    if Image is None:
        return False
    try:
        W, H = 1920, 1080
        img = Image.new("RGB", (W, H), BG_TOP)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()
        draw.text((W // 2 - 400, 200), "YESTERDAY'S QUORDLE", fill=GREEN, font=fonts['title'])
        y = (ytd_info or {}).get("yesterday", {})
        classic = y.get("classic") or []
        if classic:
            draw.text((W // 2 - 300, 400), ", ".join(w.upper() for w in classic[:4]), fill=GREEN, font=fonts['tile'])
            draw.text((W // 2 - 150, 600), str(y.get("date", "")), fill=TEXT, font=fonts['small'])
        else:
            draw.text((W // 2 - 150, 460), "(no data)", fill=TEXT, font=fonts['body'])
        draw.text((W // 2 - 300, 800), "Did you keep your streak?", fill=YELLOW, font=fonts['body'])
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception:
        return False


def generate_quordle_teaser_image(out_path, ytd_info):
    if Image is None:
        return False
    try:
        W, H = 1920, 1080
        img = Image.new("RGB", (W, H), BG_TOP)
        draw = ImageDraw.Draw(img)
        fonts = _load_fonts()
        draw.text((W // 2 - 350, 200), "TOMORROW'S TEASER", fill=GREEN, font=fonts['title'])
        t = (ytd_info or {}).get("tomorrow", {})
        classic = t.get("classic") or []
        if classic and classic[0]:
            draw.text((W // 2 - 60, 450), classic[0][0].upper(), fill=GREEN, font=fonts['big'])
            draw.text((W // 2 - 300, 650), "_ _ _ _ _  x4", fill=TEXT, font=fonts['tile'])
        else:
            draw.text((W // 2 - 150, 460), "(see you!)", fill=TEXT, font=fonts['body'])
        draw.text((W // 2 - 350, 820), "First letters revealed — subscribe!", fill=YELLOW, font=fonts['body'])
        img.save(out_path, "PNG", optimize=True)
        return True
    except Exception:
        return False


def build_optimized_title(date_short, day_num):
    variants = [
        f"Quordle Answer Today ({date_short}) - All 6 Modes Solved!",
        f"Quordle Answer Today - {date_short} Classic/Chill/Extreme Solved",
        f"Quordle Answers Today - {date_short} Full Solve + Hints",
    ]
    return variants[day_num % len(variants)]


def build_optimized_tags(date_short, date_num):
    return [
        'quordle answer today', 'Quordle', 'Quordle Answer',
        f'quordle answer today {date_num}', f'Quordle {date_short}',
        'Quordle Classic', 'Quordle Chill', 'Quordle Extreme',
        'Quordle Sequence', 'Quordle Rescue', 'Quordle Weekly',
        'Quordle Hints', 'Quordle Solver', 'Wordle', 'Daily Puzzle',
    ]


def build_captions_srt(chapters, total_duration, date_str):
    try:
        lines = []
        for i, (sec, label) in enumerate(chapters):
            start = int(sec)
            end = int(chapters[i+1][0]) if i + 1 < len(chapters) else int(total_duration)
            def _ts(s):
                return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},000"
            lines.append(str(i+1))
            lines.append(f"{_ts(start)} --> {_ts(end)}")
            lines.append(f"Quordle {date_str} - {label}")
            lines.append("")
        return "\n".join(lines)
    except Exception:
        return ""


def get_fake_date_init_script(target_iso):
    """Playwright add_init_script: freeze Date to target (time-travel trick).

    target_iso like '2026-09-27T00:00:00'. Shifts Date.now/new Date() so
    date-seeded games (quordle-likes, nerdle, etc.) serve NEXT day early.
    Keeps performance.now real to avoid breaking animations.
    """
    return f"""
(() => {{
  const SHIFT = new Date('{target_iso}').getTime() - Date.now();
  const RealDate = Date;
  function FakeDate(...args) {{
    if (args.length === 0) return new RealDate(RealDate.now() + SHIFT);
    return new RealDate(...args);
  }}
  FakeDate.now = () => RealDate.now() + SHIFT;
  FakeDate.parse = RealDate.parse;
  FakeDate.UTC = RealDate.UTC;
  FakeDate.prototype = RealDate.prototype;
  window.__TIME_SHIFT_MS = SHIFT;
  try {{ Object.defineProperty(window, 'Date', {{ value: FakeDate, configurable: true }}); }} catch(e) {{ window.Date = FakeDate; }}
}})();
"""


def apply_uniform_music_ffmpeg(video_path, script_dir, out_path=None):
    """One consistent song over full video (ffmpeg fallback, no moviepy)."""
    import subprocess
    from pathlib import Path
    try:
        sd = Path(script_dir)
        songs = [f for f in os.listdir(sd) if f.endswith('.mp3') and f.startswith('song')]
        if not songs:
            return video_path
        song = sd / random.choice(songs)
        out = out_path or str(Path(video_path).with_name(Path(video_path).stem + "_music.mp4"))
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-stream_loop", "3", "-i", str(song),
               "-shortest", "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac", "-shortest", out]
        subprocess.run(cmd, check=False, capture_output=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        return video_path
    except Exception as e:
        print(f"[music] uniform mix failed: {e}")
        return video_path
