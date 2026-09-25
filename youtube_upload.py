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


MODE_ORDER = ["Classic", "Chill", "Extreme", "Sequence", "Rescue", "Weekly"]


def build_quordle_description(today, official_map=None, chapters=None, meanings=None):
    """SEO-rich description: per-mode answers + word meanings + chapters."""
    official_map = official_map or {}
    meanings = meanings or {}
    lines = []
    lines.append(f"Today's Quordle answers for {today} - all modes solved! "
                 f"Watch the full solve for Classic, Chill, Extreme, Sequence, "
                 f"Rescue and Weekly modes.")
    lines.append("")
    lines.append("Quordle answer today: https://wordsolverx.com/quordle-answer-today")
    lines.append("Quordle solver: https://wordsolverx.com/quordle-solver")
    lines.append("")

    # Chapters (YouTube auto-links these when the first is 0:00)
    if chapters:
        lines.append("CHAPTERS:")
        for sec, label in chapters:
            m, s = divmod(int(sec), 60)
            lines.append(f"{m}:{s:02d} {label}")
        lines.append("")

    # Per-mode answers + AI meanings
    any_ans = False
    for mode in MODE_ORDER:
        words = official_map.get(mode)
        if not words:
            continue
        any_ans = True
        lines.append(f"{mode.upper()} ANSWERS: {', '.join(words)}")
        for w in words:
            mean = meanings.get(w.upper())
            if mean:
                lines.append(f"   - {w.upper()}: {mean}")
        lines.append("")
    if not any_ans:
        lines.append("Full solve for every Quordle mode. Subscribe for daily answers!")
        lines.append("")

    lines.append("#Quordle #Wordle #DailyPuzzle #BrainTeaser #WordGame #Shorts "
                 "#PuzzleSolver #WordChallenge #QuordleAnswerToday")
    lines.append("")
    lines.append("quordle answer today, quordle solver, quordle answers, how to play "
                 "quordle today, quordle classic answer today, quordle chill answer today, "
                 "quordle extreme answer today, quordle sequence answer today, "
                 "quordle rescue answer today, quordle weekly answer, best starting word "
                 "for quordle, quordle hints")
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
            # Try environment variable first (for CI)
            client_secret_env = os.environ.get('YOUTUBE_CLIENT_SECRET')
            if client_secret_env:
                try:
                    client_config = json.loads(client_secret_env)
                    # For CI, we expect the full OAuth token, not just client secret
                    if 'token' in client_config:
                        creds = Credentials.from_authorized_user_info(client_config, SCOPES)
                    else:
                        print("YOUTUBE_CLIENT_SECRET should contain full OAuth token for CI.")
                        return None
                except json.JSONDecodeError:
                    print("Invalid JSON in YOUTUBE_CLIENT_SECRET")
                    return None
            else:
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

def upload_to_youtube(video_path: str, title: str = None, description: str = None, official_map=None, chapters=None, thumbnail_path: str = None):
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
            title = f"Quordle answer for{today} - Quordle answer today #Quordle"
        
        # SEO description: per-mode answers + AI word meanings + chapters.
        if not description:
            meanings = {}
            if official_map:
                all_words = []
                for _mwords in official_map.values():
                    all_words.extend(_mwords or [])
                try:
                    meanings = fetch_word_meanings(all_words)
                    print(f"[wordinfo] fetched {len(meanings)} meanings via gemini-proxy")
                except Exception as _e:
                    print(f"[wordinfo] meanings fetch failed: {_e}")
            description = build_quordle_description(today, official_map, chapters, meanings)
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': [
                    'Quordle', 'Wordle', 'Daily Puzzle', 'Word Game', 
                    'Brain Teaser', 'Puzzle Solution', 'Shorts', 
                    'Daily Quordle', 'Today\'s Quordle'
                ],
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
