import asyncio
import os
import subprocess
import random
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import wordListsMethods

# Import YouTube upload (optional - graceful if missing)
try:
    from youtube_upload import upload_to_youtube
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    print("YouTube upload module not available.")

# Configuration
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
SONGS = ["song1.mp3", "song2.mp3"]

# Global variables (ported from quordleSolver.py)
allWords = wordListsMethods.getAllWords()
indivWords = [wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords()]
guessWord = ""
winsList = []
numLosses = 0
iteration = -1
squares = [] # Will store selectors or locators
lastWordGuessedFromList = -1
lettersUsed = [1] * 26
avgLikelihoods = wordListsMethods.totalLetterLikelihoods(wordListsMethods.getLetterLikelihoods(allWords))
knowledgeList = [[""] * 5 for _ in range(4)]
resultsList = [[""] * 5 for _ in range(4)]

# Helper Functions (Ported and adapted)

def indexOfMax(numList):
    maxVal = 0
    maxIndex = 0
    for i in range(len(numList)):
        if numList[i] > maxVal:
            maxVal = numList[i]
            maxIndex = i
    return maxIndex

def getFillerWord(lettersList):
    restWordsList = wordListsMethods.getRestWords()
    if len(lettersList) >= 4:
        for i in range(len(restWordsList)):
            if lettersList[0] in restWordsList[i] and lettersList[1] in restWordsList[i] and lettersList[2] in restWordsList[i] and lettersList[3] in restWordsList[i]:
                return restWordsList[i]
    if len(lettersList) == 3:
        for i in range(len(restWordsList)):
            if lettersList[0] in restWordsList[i] and lettersList[1] in restWordsList[i] and lettersList[2] in restWordsList[i]:
                return restWordsList[i]
    for i in range(len(restWordsList)):
        if lettersList[0] in restWordsList[i] and lettersList[1] in restWordsList[i]:
            return restWordsList[i]
    return "XXXXX"

def getMissingLetters(wordNum, ltr):
    missingIndex = ltr
    missingLetters = []
    for l in range(len(indivWords[wordNum])):
        missingLetters.append(indivWords[wordNum][l][missingIndex])
    return missingLetters

def getUnknownLetterPositions(wordList):
    unknownLtrPosList = []
    for ltr in range(5):
        thisLetter = wordList[0][ltr]
        allLettersSame = True
        for wrd in range(1, len(wordList)):
            if not (wordList[wrd][ltr] == thisLetter):
                allLettersSame = False
        if not allLettersSame:
            unknownLtrPosList.append(ltr)
    return unknownLtrPosList

def minLenNot0():
    minLen = len(indivWords[0])
    for i in range(1, 4):
        if len(indivWords[i]) > minLen:
            minLen = len(indivWords[i])
    for i in range(4):
        if len(indivWords[i]) != 0 and len(indivWords[i]) < minLen:
            minLen = len(indivWords[i])
    return minLen

def findBestWord():
    for i in range(4):
        if len(indivWords[i]) == 1:
            resultsList[i] = ["C", "C", "C", "C", "C"]
            print("Found word: ", indivWords[i][0], " --- Iteration: ", iteration + 1)
            return indivWords[i][0]

    combinedWordsList = []
    wordsLeft = 0
    for i in range(4):
        if knowledgeList[i] == ["D", "D", "D", "D", "D"]:
            wordsLeft += 1

    for i in range(4):
        if len(indivWords[i]) > 0:
            dCount = 0
            for j in range(5):
                if knowledgeList[i][j] == "D":
                    dCount += 1
            unknownLetterPosns = getUnknownLetterPositions(indivWords[i])
            if len(unknownLetterPosns) == 1 and len(indivWords[i]) > 2 and iteration != 7:
                missingLetters = getMissingLetters(i, unknownLetterPosns[0])
                combinedWordsList.append(getFillerWord(missingLetters))
            elif len(unknownLetterPosns) == 2 and "M" not in resultsList[i] and wordsLeft > 1:
                missingLetters = getMissingLetters(i, unknownLetterPosns[0])
                missingLetters.extend(getMissingLetters(i, unknownLetterPosns[1]))
                missingLetters = list(set(missingLetters))
                combinedWordsList.append(getFillerWord(missingLetters))
            else:
                for j in range(len(indivWords[i])):
                    combinedWordsList.append(indivWords[i][j])

    wordValueList = []
    likelihoods = wordListsMethods.getLetterLikelihoods(combinedWordsList)

    for i in range(5):
        for j in range(26):
            likelihoods[i][j] += (avgLikelihoods[j] * lettersUsed[j])

    for i in range(len(combinedWordsList)):
        curWordValue = 0
        for j in range(5):
            curLetter = combinedWordsList[i][j]
            curLetterIndex = wordListsMethods.letters.index(curLetter)
            dupeFactor = 1
            if len(wordListsMethods.getDupsIndexList(j, combinedWordsList[i])) == 2:
                dupeFactor = 2/3
            elif len(wordListsMethods.getDupsIndexList(j, combinedWordsList[i])) == 3:
                dupeFactor = 0.5
            curWordValue += (likelihoods[j][curLetterIndex] * dupeFactor)

        if iteration > 0:
            inListCounter = 0
            for a in range(4):
                if combinedWordsList[i] in indivWords[a]:
                    inListCounter += 1
            for b in range(4):
                if minLenNot0() == len(indivWords[b]) and inListCounter == 1 and combinedWordsList[i] in indivWords[b] and wordsLeft > 1:
                    curWordValue = 0
        wordValueList.append(curWordValue)
    return combinedWordsList[indexOfMax(wordValueList)]

def setLettersAsUsed(wrd):
    for i in range(5):
        curLetter = wrd[i]
        curLetterIndex = wordListsMethods.letters.index(curLetter)
        lettersUsed[curLetterIndex] = 0

def removeWords():
    global allWords
    global indivWords
    lastWord = guessWord
    for word in range(4):
        if lastWord in indivWords[word]:
            indivWords[word].remove(lastWord)
            if indivWords[word] == []:
                continue
        if resultsList[word] == ["C", "C", "C", "C", "C"]:
            indivWords[word] = []
            continue
        for letter in range(5):
            wordListCopy = []
            for a in range(len(indivWords[word])):
                wordListCopy.append(indivWords[word][a])
            if resultsList[word][letter] == "I":
                sameLetterIndexList = wordListsMethods.getDupsIndexList(letter, lastWord)
                if len(sameLetterIndexList) > 1:
                    sameLetterResultsList = []
                    for b in range(len(sameLetterIndexList)):
                        sameLetterResultsList.append(resultsList[word][sameLetterIndexList[b]])
                    if "M" in sameLetterResultsList or "C" in sameLetterResultsList:
                        for j in range(len(wordListCopy)):
                            if wordListCopy[j][letter] == lastWord[letter]:
                                indivWords[word].remove(wordListCopy[j])
                else:
                    for i in range(len(wordListCopy)):
                        if wordListsMethods.wordContains(wordListCopy[i], lastWord[letter]):
                            indivWords[word].remove(wordListCopy[i])
            elif resultsList[word][letter] == "M":
                for i in range(len(wordListCopy)):
                    if wordListCopy[i][letter] == lastWord[letter]:
                        indivWords[word].remove(wordListCopy[i])
                        continue
                    if not wordListsMethods.wordContains(wordListCopy[i], lastWord[letter]):
                        indivWords[word].remove(wordListCopy[i])
            else:
                for i in range(len(wordListCopy)):
                    if wordListCopy[i][letter] != lastWord[letter]:
                        indivWords[word].remove(wordListCopy[i])

# Async functions for Playwright

async def init_squares(page):
    """
    Simulate the squares setup from Selenium, but using Playwright locators.
    We'll generate the XPath strings dynamically since we can't store 'Elements' like in Selenium easily.
    """
    return

async def get_square_color(page, i_idx, j_idx, row_idx, k_idx):
    """
    Mapping:
    i, j determine the quadrant (0-3).
    row is the row in that quadrant (1-9).
    k is the letter position (1-5).
    """
    quadrant = 0
    if i_idx == 1 and j_idx == 1:
        quadrant = 0
    elif i_idx == 1 and j_idx == 2:
        quadrant = 1
    elif i_idx == 2 and j_idx == 1:
        quadrant = 2
    else:
        quadrant = 3
    
    # XPath from original: '//*[@id="game-board-row-' + str(i) + '"]/div[' + str(j) + ']/div[' + str(row) + ']/div[' + str(k) + ']'
    # Note: 'row' in the loop 'for row in range(1, 10)' refers to the turn number (guess 1-9).
    # But in the XPath, it is nested:
    # id="game-board-row-1" (or 2) -> div[1] (or 2) -> div[row] -> div[k]
    
    # Let's reconstruct the selector.
    # i_idx: 1 or 2 (Row of boards)
    # j_idx: 1 or 2 (Column of boards)
    # row_idx: 1 to 9 (The attempt number)
    # k_idx: 1 to 5 (The letter position)
    
    xpath = f'//*[@id="game-board-row-{i_idx}"]/div[{j_idx}]/div[{row_idx}]/div[{k_idx}]'
    
    # Evaluate background color
    try:
        color = await page.locator(xpath).evaluate("e => getComputedStyle(e).backgroundColor")
        print(f"DEBUG: {xpath} -> {color}")
        return color
    except Exception as e:
        print(f"Error getting color for {xpath}: {e}")
        # Dump part of the HTML to see what's wrong
        try:
             # Just dump the board 1 row 1
             if i_idx == 1 and j_idx == 1 and row_idx == 1 and k_idx == 1:
                  html = await page.content()
                  with open("page_dump.html", "w", encoding="utf-8") as f:
                       f.write(html)
                  print("Dumped page content to page_dump.html")
        except:
             pass
        return "rgba(0, 0, 0, 0)"

async def changeResultsListAsync(page):
    global resultsList
    global knowledgeList
    global iteration
    
    current_xpath_row = iteration + 1
    
    board_idx = 0
    for i in range(1, 3):
        for j in range(1, 3):
            for k in range(1, 6):
                color = await get_square_color(page, i, j, current_xpath_row, k)
                
                # Check based on RGB values found in color string
                if "0, 204, 136" in color: # Green
                    resultsList[board_idx][k-1] = "C"
                    knowledgeList[board_idx][k-1] = "D"
                elif "255, 204, 0" in color: # Yellow
                    resultsList[board_idx][k-1] = "M"
                elif "228, 228, 231" in color: # Gray (incorrect letter)
                    resultsList[board_idx][k-1] = "I"
                elif "244, 244, 245" in color: # Unfilled tile (board already solved)
                    # This board is already solved, skip it
                    pass
                else:
                    print(f"WARNING: Unknown color encountered: {color}")
                    pass
            board_idx += 1

async def block_ads(route):
    # Block common ad resources to speed up loading
    url = route.request.url
    if any(x in url for x in ["googlesyndication", "doubleclick", "ads", "adnxs", "moatads"]):
        await route.abort()
    else:
        await route.continue_()

async def main():
    global guessWord
    global lastWordGuessedFromList
    global iteration
    global winsList
    global numLosses
    global indivWords
    global resultsList
    global knowledgeList
    global lettersUsed
    
    # Determine script directory for song paths
    script_dir = Path(__file__).parent
    video_dir = script_dir / "videos"
    video_dir.mkdir(exist_ok=True)
    
    async with async_playwright() as p:
        # Browser setup with video
        print(f"Starting browser (headless={HEADLESS})...")
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        
        # Enable ad blocking
        await context.route("**/*", block_ads)
        
        page = await context.new_page()
        
        # Set a standard User-Agent to avoid being flagged/blocked
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Navigate to Quordle with longer timeout and faster wait strategy
        print("Navigating to Quordle...")
        try:
            await page.goto("https://www.merriam-webster.com/games/quordle", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Initial navigation warning: {e}. Attempting to continue...")
        
        # Wait for game to load (look for simple element)
        try:
             await page.wait_for_selector('//*[@id="game-board-row-1"]', timeout=30000)
        except:
             print("Timeout waiting for game board. Initializing anyway...")

        # Optional: Handle "How to play" popup if it exists
        await page.mouse.click(10, 10) # Click somewhere safe to dismiss overlay
        await asyncio.sleep(1)

        # Single game (for daily run - no repeat)
        # Reset variables for new game
        indivWords = [wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords()]
        resultsList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
        knowledgeList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
        lettersUsed = [1] * 26
        iteration = -1
        
        # Play 9 rounds
        for i in range(10):
            if i == 9:
                numLosses += 1
                break
            
            # Logic to find best word
            guessWord = findBestWord()
            
            setLettersAsUsed(guessWord)
            
            # Track what list we guessed from
            for idx in range(4):
                for w in indivWords[idx]:
                    if guessWord == w:
                        lastWordGuessedFromList = idx
            
            print(f"Guessing: {guessWord}")
            
            # Input the word
            await page.keyboard.type(guessWord)
            await page.keyboard.press("Enter")
            
            # Wait for animation/reveal
            await asyncio.sleep(2.7)
            
            iteration += 1
            
            # Check results
            await changeResultsListAsync(page)
            
            # Remove words based on results
            removeWords()
            
            # Check for win
            if resultsList == [["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"]]:
                winsList.append(i+1)
                print("WIN!")
                break
        
        # Post-game wrap up
        print(f"Wins: {len(winsList)} - Losses: {numLosses}")
        
        await asyncio.sleep(3)
        
        # Close browser to finalize video
        await context.close()
        await browser.close()
        
        # Get the latest video file
        video_path = await page.video.path()
        print(f"Raw video saved: {video_path}")
    
    # Post-processing: Add background music
    final_video_path = add_background_music(video_path, script_dir, video_dir)
    
    # Upload to YouTube
    if YOUTUBE_AVAILABLE and final_video_path:
        today = datetime.now().strftime("%B %d, %Y")
        title = f"Quordle {today} - Daily Puzzle Solved!"
        upload_to_youtube(str(final_video_path), title=title)
    else:
        print("Skipping YouTube upload.")
    
    print("Done!")


def add_background_music(video_path: str, script_dir: Path, video_dir: Path) -> Path:
    """Add random background music to the video using ffmpeg."""
    # Pick a random song
    song_name = random.choice(SONGS)
    song_path = script_dir / song_name
    
    if not song_path.exists():
        print(f"Song not found: {song_path}. Skipping music.")
        return Path(video_path)
    
    # Output file with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = video_dir / f"quordle_{timestamp}.mp4"
    
    print(f"Adding background music: {song_name}")
    
    # ffmpeg command: merge video + audio, loop audio
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1", "-i", str(song_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"Final video with music: {output_path}")
            # Clean up raw video
            try:
                Path(video_path).unlink()
            except:
                pass
            return output_path
        else:
            print(f"ffmpeg error: {result.stderr}")
            return Path(video_path)
    except FileNotFoundError:
        print("ffmpeg not found. Please install ffmpeg: https://ffmpeg.org/download.html")
        print("On Windows, you can use: winget install ffmpeg")
        return Path(video_path)
    except subprocess.TimeoutExpired:
        print("ffmpeg timed out.")
        return Path(video_path)


if __name__ == "__main__":
    asyncio.run(main())
