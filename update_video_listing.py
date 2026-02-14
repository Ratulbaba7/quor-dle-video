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
            # print(result.stdout) # Optional: too noisy?
            return result.stdout.strip()
        else:
            print(f"ERROR: Command '{command}' failed with return code {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return None
    except Exception as e:
        print(f"EXCEPTION running {command}: {e}")
        return None

def update_video_repo(video_id):
    # 1. Setup Authentication URL
    pat = os.environ.get("VIDEO_REPO_PAT")
    if not pat:
        print("ERROR: VIDEO_REPO_PAT environment variable not found.")
        print("Please add the PAT as a secret in GitHub Actions.")
        return

    auth_url = REPO_URL.replace("https://", f"https://{pat}@")
    
    # 2. Create a temporary directory for the clone
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "video-repo")
        
        # 3. Clone the repo
        print(f"Cloning repo to temporary directory...")
        if not run_command(f"git clone {auth_url} {repo_path}"):
            return
            
        # 4. Create/Verify Target Directory
        target_path = os.path.join(repo_path, TARGET_DIR)
        if not os.path.exists(target_path):
            os.makedirs(target_path)
            
        # 5. Create JSON File
        today = datetime.now().strftime("%Y-%m-%d")
        json_filename = f"{today}.json"
        json_path = os.path.join(target_path, json_filename)
        
        data = {
            "id": video_id,
            "date": today,
            "platform": "youtube",
            "type": "daily-solve"
        }
        
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
            
        print(f"Created {json_filename} with video ID: {video_id}")
        
        # 6. Git Config (Needed for CI)
        run_command('git config user.name "Wordsolver Robot"', cwd=repo_path)
        run_command('git config user.email "robot@wordsolverx.com"', cwd=repo_path)
        
        # 7. Commit and Push
        print("Committing and pushing changes...")
        run_command("git add .", cwd=repo_path)
        # Check if there are actually changes to commit
        status = run_command("git status --porcelain", cwd=repo_path)
        if not status:
            print("No changes to commit (file already exists and is identical).")
            return
            
        if run_command(f'git commit -m "Add Quordle video for {today}"', cwd=repo_path):
            run_command("git push origin main", cwd=repo_path)
            print("Successfully pushed to wordsolverx-videos/video!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_video_listing.py <video_id>")
        sys.exit(1)
    
    video_id = sys.argv[1]
    update_video_repo(video_id)
