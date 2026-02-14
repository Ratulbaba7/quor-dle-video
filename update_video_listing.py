import os
import sys
import json
import subprocess
import shutil
import tempfile
from datetime import datetime

# Configuration
REPO_URL = "https://github.com/wordsolverx-videos/video.git"
TARGET_DIR = "quordle"

def run_command(command, cwd=None):
    print(f"DEBUG: Executing '{command}' in '{cwd}'")
    try:
        # Use shell=True for windows compatibility and easier command chaining
        result = subprocess.run(
            command, cwd=cwd, shell=True, text=True, capture_output=True
        )
        if result.returncode == 0:
            print(f"Success: {command}")
            return True
        else:
            print(f"ERROR: Command '{command}' failed with return code {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"EXCEPTION running {command}: {e}")
        return False

def update_video_repo(video_id):
    # 1. Setup Authentication URL
    pat = os.environ.get("VIDEO_REPO_PAT")
    if not pat:
        print("ERROR: VIDEO_REPO_PAT environment variable not found.")
        sys.stdout.flush()
        return

    auth_url = REPO_URL.replace("https://", f"https://{pat}@")
    
    # 2. Create a temporary directory for the clone
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "video-repo")
        
        # 3. Clone the repo
        print(f"DEBUG: Cloning to {repo_path}...")
        sys.stdout.flush()
        
        # Clone heavily, ensure we get main branch
        if not run_command(f"git clone {auth_url} {repo_path}"):
            print("ERROR: Clone failed")
            return
            
        # 4. Create/Verify Target Directory
        target_path = os.path.join(repo_path, TARGET_DIR)
        if not os.path.exists(target_path):
            os.makedirs(target_path)
            
        print(f"DEBUG: Target path is {target_path}")

        # 5. Create JSON File
        today = datetime.now().strftime("%Y-%m-%d")
        json_filename = f"{today}.json"
        json_path = os.path.join(target_path, json_filename)
        
        data = {
            "id": video_id,
            "date": today,
            "url": f"https://www.youtube.com/watch?v={video_id}"
        }
        
        # Write file
        try:
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"DEBUG: Wrote JSON to {json_path}")
        except Exception as e:
            print(f"ERROR: Failed to write JSON: {e}")
            return
            
        # 6. Git Config (Needed for CI)
        run_command('git config user.name "Wordsolver Robot"', cwd=repo_path)
        run_command('git config user.email "robot@wordsolverx.com"', cwd=repo_path)
        
        # 7. Commit and Push
        print("DEBUG: Staging changes...")
        run_command("git add .", cwd=repo_path)
        
        print("DEBUG: Committing...")
        # Force commit even if empty just to see what happens (allow-empty is for debug)
        commit_msg = f"Add Quordle video for {today}"
        if run_command(f'git commit -m "{commit_msg}"', cwd=repo_path):
            print("DEBUG: Pushing to origin main...")
            # Explicitly force push to main to avoid detached head issues
            push_result = run_command("git push origin main", cwd=repo_path)
            if push_result is not None:
                print("SUCCESS: Pushed to wordsolverx-videos/video")
            else:
                print("ERROR: Push failed")
        else:
            print("ERROR: Commit failed (nothing to commit?)")
            
        sys.stdout.flush()

if __name__ == "__main__":
    print("DEBUG: update_video_listing.py started...")
    sys.stdout.flush()
    
    if len(sys.argv) < 2:
        print("Usage: python update_video_listing.py <video_id>")
        sys.exit(1)
    
    video_id = sys.argv[1]
    print(f"DEBUG: Received video_id: {video_id}")
    update_video_repo(video_id)
