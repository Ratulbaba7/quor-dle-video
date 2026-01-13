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

def upload_to_youtube(video_path: str, title: str = None, description: str = None):
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
            title = f"Quordle {today} - Daily Solve! #Shorts #Quordle"
        
        # Proper SEO Description
        if not description:
            description = f"""Daily Quordle solve for {today}! Watch the full solution for today's puzzle. 

#Quordle #Wordle #DailyPuzzle #BrainTeaser #WordGame #Shorts #PuzzleSolver #WordChallenge

Quordle is a word game where you solve four 5-letter puzzles at once. Subscribe for daily solutions!"""
        
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
