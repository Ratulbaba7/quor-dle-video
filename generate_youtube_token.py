import os
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def generate_token():
    """
    Generates a YouTube OAuth token and prints it in JSON format.
    The output should be added as a GitHub Secret named YOUTUBE_CLIENT_SECRET.
    """
    # Check for client secret file
    client_secret_files = ['client-secret.json', 'client_secret.json']
    client_secret_path = None
    
    for filename in client_secret_files:
        path = Path(__file__).parent / filename
        if path.exists():
            client_secret_path = path
            break
    
    if not client_secret_path:
        print("Error: client-secret.json not found in the current directory.")
        print("Please download your OAuth 2.0 Client ID JSON from Google Cloud Console.")
        return

    print(f"Using client secret from: {client_secret_path.name}")
    
    try:
        # Create flow and run local server for authentication
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), SCOPES
        )
        
        # This will open a browser window for authentication
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message='Please visit this URL to authorize this application: {url}',
            success_message='The authentication flow has completed; you may close this window.'
        )
        
        # Convert credentials to authorized user info (JSON format)
        creds_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        output_path = Path(__file__).parent / 'youtube_token.json'
        with open(output_path, 'w') as f:
            json.dump(creds_data, f, indent=2)
            
        print("\n" + "="*50)
        print("SUCCESS! TOKEN SAVED TO FILE:")
        print(f"File: {output_path.name}")
        print("="*50 + "\n")
        print("You can now find the JSON content in 'youtube_token.json'.")
        print("Add the entire content of that file as a GitHub Secret named: YOUTUBE_CLIENT_SECRET")
        print("="*50)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    generate_token()
