"""
YouTube Upload Module
Uploads videos to YouTube using OAuth2 credentials.
Gracefully skips if no credentials are found.
"""

import os
import json
import pickle
from pathlib import Path
from datetime import datetime

# Check if google libraries are available
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    print("YouTube upload libraries not installed. Skipping upload functionality.")

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Broader scopes enable thumbnail set + playlists when the token allows it.
SCOPES_FULL = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

import requests as _rq

GEMINI_PROXY_URL = "https://gemini-web-proxy.shonratt.workers.dev/v1/chat/completions"
GEMINI_PROXY_MODEL = "gemini-3.6-flash"


def _gemini_chat(prompt, timeout=30):
    try:
        r = _rq.post(GEMINI_PROXY_URL,
                     json={"model": GEMINI_PROXY_MODEL,
                           "messages": [{"role": "user", "content": prompt}]},
                     headers={"Content-Type": "application/json"}, timeout=timeout)
        r.raise_for_status()
        return (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    except Exception as e:
        print(f"[gemini] request failed: {e}")
        return ""


def fetch_word_meanings(words, timeout=40):
    """Return {WORD: 'one-line meaning'} for a list of words via one AI call.

    Batches all words into a single prompt for speed. Returns {} on failure.
    """
    import json as _json
    words = [w.strip().upper() for w in words if w and len(w.strip()) == 5]
    words = list(dict.fromkeys(words))  # dedupe, keep order
    if not words:
        return {}
    prompt = (
        "Return ONLY minified JSON: an object mapping each WORD to one short "
        "family-friendly definition sentence. No prose, no code fences. "
        "Words: " + ", ".join(words)
    )
    content = _gemini_chat(prompt)
    if not content:
        return {}
    t = content.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        obj = _json.loads(t[start:end + 1])
    except Exception:
        return {}
    out = {}
    for k, v in obj.items():
        ku = str(k).strip().upper()
        if len(ku) == 5:
            out[ku] = str(v).strip()
    return out


def fetch_word_analysis(words, timeout=45):
    """Rich per-word analysis like Wordle's fetch_word_info_ai.

    Returns {WORD: {part_of_speech, definition, example}} via one batched
    AI call. Falls back to the simpler fetch_word_meanings on failure.
    """
    import json as _json
    words = [w.strip().upper() for w in words if w and len(w.strip()) == 5]
    words = list(dict.fromkeys(words))
    if not words:
        return {}
    prompt = (
        "Return ONLY minified JSON: an object mapping each WORD to an object "
        "with keys part_of_speech, definition (one sentence), example (a short "
        "family-friendly example sentence using the word). No prose, no code "
        "fences. Words: " + ", ".join(words)
    )
    content = _gemini_chat(prompt, timeout=timeout)
    if not content:
        return {}
    t = content.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        obj = _json.loads(t[start:end + 1])
    except Exception:
        return {}
    out = {}
    for k, v in obj.items():
        ku = str(k).strip().upper()
        if len(ku) == 5 and isinstance(v, dict):
            out[ku] = {
                "part_of_speech": str(v.get("part_of_speech", "")).strip(),
                "definition": str(v.get("definition", "")).strip(),
                "example": str(v.get("example", "")).strip(),
            }
    return out


MODE_ORDER = ["Classic", "Chill", "Extreme", "Sequence", "Rescue", "Weekly"]


def build_quordle_description(today, official_map=None, chapters=None,
                            meanings=None, ytd_info=None, analysis=None):
    """SEO-rich description matching Wordle-level quality.

    Includes: keyword headline, real chapters, FAQ quick-answers block,
    per-mode answers + AI definitions, yesterday recap / tomorrow teaser,
    puzzle stats, and keyword-optimized hashtags.
    """
    official_map = official_map or {}
    meanings = meanings or {}
    ytd_info = ytd_info or {}
    analysis = analysis or {}
    lines = []

    # Headline (exact match keyword first)
    classic = official_map.get("Classic") or []
    classic_str = ", ".join(classic) if classic else "watch to reveal"
    lines.append("🎲 Quordle Answer Today — " + today + " | All 6 Modes Solved 🎲")
    lines.append("")
    lines.append(
        f"Today's Quordle Classic answers: {classic_str}. "
        "Watch the full solve for Classic, Chill, Extreme, Sequence, "
        "Rescue and Weekly modes — every puzzle solved with hints!"
    )
    lines.append("")
    lines.append("Quordle answer today: https://wordsolverx.com/quordle-answer-today")
    lines.append("Quordle solver: https://wordsolverx.com/quordle-solver")
    lines.append("")

    # Chapters (YouTube auto-links these when the first is 0:00)
    if chapters:
        lines.append("⏱️ CHAPTERS:")
        for sec, label in chapters:
            m, s = divmod(int(sec), 60)
            lines.append(f"{m}:{s:02d} {label}")
        lines.append("")

    # FAQ quick-answers block (captures long-tail voice queries)
    faq = ["❓ What is today's Quordle answer? ➤ " +
           (", ".join(classic) if classic else "Watch the video!")]
    if ytd_info.get("yesterday"):
        _y = ytd_info["yesterday"]
        _yc = _y.get("classic") or []
        if _yc:
            faq.append("❓ What was yesterday's Quordle answer? ➤ " +
                       ", ".join(_yc))
    lines.append("💡 QUICK ANSWERS:")
    lines.extend(faq)
    lines.append("")

    # Per-mode answers + AI definitions
    any_ans = False
    for mode in MODE_ORDER:
        words = official_map.get(mode)
        if not words:
            continue
        any_ans = True
        lines.append(f"🔓 {mode.upper()} ANSWERS: {', '.join(words)}")
        for w in words:
            wu = w.upper()
            a = analysis.get(wu)
            if a:
                pos = a.get("part_of_speech", "")
                defn = a.get("definition", "")
                ex = a.get("example", "")
                if defn:
                    pos_s = f" ({pos})" if pos else ""
                    lines.append(f"   📖 {wu}{pos_s}: {defn}")
                if ex:
                    lines.append(f'      Example: "{ex}"')
            else:
                mean = meanings.get(wu)
                if mean:
                    lines.append(f"   📖 {wu}: {mean}")
        lines.append("")

    if not any_ans:
        lines.append("Full solve for every Quordle mode. Subscribe for daily answers!")
        lines.append("")

    # Yesterday recap + tomorrow teaser
    if ytd_info.get("yesterday"):
        _y = ytd_info["yesterday"]
        _yc = _y.get("classic") or []
        if _yc:
            lines.append(f"📅 YESTERDAY'S QUORDLE: {', '.join(_yc)}")
            lines.append("")
    if ytd_info.get("tomorrow"):
        _t = ytd_info["tomorrow"]
        _tc = _t.get("classic") or []
        if _tc:
            _first = _tc[0] if _tc else "?"
            lines.append(
                f"🔮 TOMORROW'S QUORDLE: First Classic word starts "
                f"with '{_first[0].upper()}'")
            lines.append("")

    # Stats
    _mode_count = sum(1 for m in MODE_ORDER if official_map.get(m))
    lines.append("📊 PUZZLE STATS:")
    lines.append(f"   🗓️ Date: {today}")
    lines.append(f"   🎮 Modes solved: {_mode_count}/6")
    if classic:
        lines.append(f"   ✅ Classic answers: {', '.join(classic)}")
    lines.append("")

    lines.append("🔔 Subscribe for a new Quordle answer every day — never lose your streak!")
    lines.append("")
    lines.append("🧠 Try our FREE Quordle Solver:")
    lines.append("🔗 https://wordsolverx.com/quordle-solver")
    lines.append("")
    lines.append("#Quordle #QuordleAnswerToday #QuordleAnswer #Wordle #DailyPuzzle "
                 "#BrainTeaser #WordGame #Shorts #PuzzleSolver #WordChallenge "
                 "#QuordleHints #QuordleSolver")
    lines.append("")
    lines.append("quordle answer today, quordle solver, quordle answers, how to play "
                 "quordle today, quordle classic answer today, quordle chill answer today, "
                 "quordle extreme answer today, quordle sequence answer today, "
                 "quordle rescue answer today, quordle weekly answer, best starting word "
                 "for quordle, quordle hints, quordle answers today")
    lines.append("")
    lines.append("Quordle is a word game where you solve four 5-letter puzzles at once. "
                 "Subscribe for daily solutions!")
    return "\n".join(lines)

def get_credentials():
    """
    Get YouTube API credentials from:
    1. Environment variable YOUTUBE_CLIENT_SECRET (for CI)
    2. Local client_secret.json file
    Returns None if neither is available.
    """
    if not GOOGLE_LIBS_AVAILABLE:
        return None
    
    creds = None
    token_path = Path(__file__).parent / 'token.pickle'
    
    # Check for existing token
    if token_path.exists():
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid creds, try to get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh credentials: {e}")
                creds = None
        
        if not creds:
            # PREFERRED (same as the Wordle repo -> SAME YouTube channel):
            # three separate secrets. Whatever channel the refresh token was
            # minted on is the channel the video lands on, so reusing the
            # Wordle repo's YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN
            # guarantees Wordle and Quordle upload to the SAME channel.
            rid = os.environ.get('YOUTUBE_CLIENT_ID', '').strip()
            rsecret = os.environ.get('YOUTUBE_CLIENT_SECRET', '').strip()
            rtok = os.environ.get('YOUTUBE_REFRESH_TOKEN', '').strip()
            if rid and rtok and rsecret and not rsecret.lstrip().startswith('{'):
                try:
                    creds = Credentials.from_authorized_user_info({
                        'client_id': rid,
                        'client_secret': rsecret,
                        'refresh_token': rtok,
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'scopes': SCOPES,
                    }, SCOPES)
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    print("[youtube] Using 3-part refresh-token creds (same channel as Wordle).")
                except Exception as e:
                    print(f"[youtube] 3-part cred build failed: {e}")
                    creds = None

            # FALLBACK: single full-OAuth-JSON in YOUTUBE_CLIENT_SECRET (legacy).
            client_secret_env = os.environ.get('YOUTUBE_CLIENT_SECRET')
            if not creds and client_secret_env and client_secret_env.lstrip().startswith('{'):
                try:
                    client_config = json.loads(client_secret_env)
                    if 'token' in client_config or 'refresh_token' in client_config:
                        creds = Credentials.from_authorized_user_info(client_config, SCOPES)
                    else:
                        print("YOUTUBE_CLIENT_SECRET JSON lacks token/refresh_token.")
                        return None
                except json.JSONDecodeError:
                    print("Invalid JSON in YOUTUBE_CLIENT_SECRET")
                    return None

            if not creds:
                # Try local client_secret.json or client-secret.json
                client_secret_path = Path(__file__).parent / 'client-secret.json'
                if not client_secret_path.exists():
                    client_secret_path = Path(__file__).parent / 'client_secret.json'
                
                if client_secret_path.exists():
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(client_secret_path), SCOPES
                        )
                        creds = flow.run_local_server(port=0)
                    except Exception as e:
                        print(f"Failed to authenticate: {e}")
                        return None
                else:
                    print("No YouTube credentials found. Skipping upload.")
                    return None
        
        # Save credentials for next run
        if creds:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
    
    return creds

def youtube_find_or_create_playlist(youtube, title, description=""):
    try:
        r = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for it in r.get("items", []):
            if it["snippet"]["title"].strip().lower() == title.strip().lower():
                return it["id"]
        r = youtube.playlists().insert(part="snippet,status",
            body={"snippet": {"title": title, "description": description},
                  "status": {"privacyStatus": "public"}}).execute()
        return r.get("id")
    except Exception as e:
        print(f"[playlist] find/create failed: {e}")
        return None


def youtube_add_to_playlist(youtube, playlist_id, video_id):
    try:
        youtube.playlistItems().insert(part="snippet",
            body={"snippet": {"playlistId": playlist_id,
                              "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        print(f"[playlist] added {video_id}")
    except Exception as e:
        print(f"[playlist] add failed: {e}")


def youtube_pin_comment(youtube, video_id, text):
    try:
        t = youtube.commentThreads().insert(part="snippet",
            body={"snippet": {"videoId": video_id,
                              "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
        cid = t.get("id")
        # pin not directly supported via API v3 for all; best-effort like
        return cid
    except Exception as e:
        print(f"[comment] pin failed (scope?): {e}")
        return None


def youtube_upload_captions(youtube, video_id, srt_text):
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
            f.write(srt_text)
            p = f.name
        from googleapiclient.http import MediaFileUpload as _MFU
        youtube.captions().insert(part="snippet",
            body={"snippet": {"videoId": video_id, "language": "en", "name": "English"}},
            media_body=_MFU(p)).execute()
        print("[captions] uploaded")
    except Exception as e:
        print(f"[captions] failed (scope?): {e}")


def upload_to_youtube(video_path: str, title: str = None, description: str = None,
                      official_map=None, chapters=None, thumbnail_path: str = None,
                      ytd_info=None, tags=None):
    """
    Upload a video to YouTube.
    Returns video ID if successful, None otherwise.
    """
    creds = get_credentials()
    if not creds:
        print("Skipping YouTube upload - no credentials available.")
        return None
    
    try:
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Generate title and description if not provided
        today = datetime.now().strftime("%B %d, %Y")
        if not title:
            title = f"Quordle Answer Today ({today}) - All 6 Modes Solved!"
        
        # SEO description: per-mode answers + AI word meanings + chapters.
        if not description:
            meanings = {}
            analysis = {}
            if official_map:
                all_words = []
                for _mwords in official_map.values():
                    all_words.extend(_mwords or [])
                try:
                    analysis = fetch_word_analysis(all_words)
                    print(f"[wordinfo] fetched {len(analysis)} rich analyses via gemini-proxy")
                except Exception as _e:
                    print(f"[wordinfo] analysis fetch failed: {_e}")
                # Fallback: simple one-liners for anything the rich call missed
                _missing = [w for w in all_words
                            if w and len(w) == 5 and w.upper() not in analysis]
                if _missing:
                    try:
                        meanings = fetch_word_meanings(_missing)
                        print(f"[wordinfo] fallback meanings for {len(meanings)} words")
                    except Exception as _e:
                        print(f"[wordinfo] fallback meanings failed: {_e}")
            description = build_quordle_description(
                today, official_map, chapters, meanings, ytd_info, analysis)
        
        try:
            import quordle_parity as _QP
            _ds = today.split(",")[0]
            _dn = today.replace(",", "").split()[:2]
            _date_num = "/".join(_dn) if len(_dn) == 2 else _ds
            _tags = _QP.build_optimized_tags(_ds, _date_num)
        except Exception:
            _tags = [
                'Quordle', 'Quordle Answer Today', 'Quordle Answer',
                'Wordle', 'Daily Puzzle', 'Word Game',
                'Brain Teaser', 'Puzzle Solution', 'Shorts',
                'Daily Quordle', "Today's Quordle", 'Quordle Hints',
                'Quordle Solver', 'Quordle Classic', 'Quordle Chill',
                'Quordle Extreme', 'Quordle Sequence', 'Quordle Rescue',
            ]
        # YouTube snippet.description max is 5000 chars (400 invalidDescription)
        if len(description) > 5000:
            _orig = len(description)
            _cut = description[:5000].rsplit("\n", 1)[0]
            description = _cut if _cut else description[:5000]
            print(f"[desc] capped {_orig} -> {len(description)} chars")
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or _tags,
                'categoryId': '20'  # Gaming
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False,
                'embeddable': True,
                'license': 'youtube'
            }
        }
        
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        print(f"Uploading video: {title}")
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = request.execute()
        video_id = response.get('id')
        print(f"Upload successful! Video ID: {video_id}")
        print(f"URL: https://www.youtube.com/watch?v={video_id}")
        # Best-effort custom thumbnail (needs youtube scope; ignore on failure)
        if thumbnail_path and video_id:
            try:
                import os as _os
                if _os.path.exists(thumbnail_path):
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(thumbnail_path)
                    ).execute()
                    print(f"[thumbnail] set custom thumbnail: {thumbnail_path}")
            except Exception as _te:
                print(f"[thumbnail] set failed (scope?): {_te}")
        # Wordle-parity enrichment: playlist + pin + captions (best-effort)
        try:
            _pl = youtube_find_or_create_playlist(youtube, "Quordle Answer Today - Daily", "Daily Quordle answers - all modes solved")
            if _pl:
                youtube_add_to_playlist(youtube, _pl, video_id)
        except Exception:
            pass
        try:
            _classic = ((official_map or {}).get("Classic") or [])
            _pin = "Today's Classic: " + (", ".join(_classic) if _classic else "watch to reveal") + " | Solver: https://wordsolverx.com/quordle-solver"
            youtube_pin_comment(youtube, video_id, _pin)
        except Exception:
            pass
        try:
            if chapters:
                import quordle_parity as _QP2
                _srt = _QP2.build_captions_srt(chapters, chapters[-1][0] + 30 if chapters else 300, today)
                if _srt:
                    youtube_upload_captions(youtube, video_id, _srt)
        except Exception:
            pass
        return video_id
        
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        return None


if __name__ == "__main__":
    # Test upload
    import sys
    if len(sys.argv) > 1:
        upload_to_youtube(sys.argv[1])
    else:
        print("Usage: python youtube_upload.py <video_path>")
