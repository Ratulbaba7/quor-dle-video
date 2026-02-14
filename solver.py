import asyncio
import os
import subprocess
import random
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import re
import json
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

# Game modes configuration
GAME_MODES = [
    {"name": "Classic", "url": "https://www.merriam-webster.com/games/quordle/#/"},
    {"name": "Chill", "url": "https://www.merriam-webster.com/games/quordle/#/chill"},
    {"name": "Extreme", "url": "https://www.merriam-webster.com/games/quordle/#/extreme"},
    {"name": "Rescue", "url": "https://www.merriam-webster.com/games/quordle/#/rescue"},
    {"name": "Sequence", "url": "https://www.merriam-webster.com/games/quordle/#/sequence"},
    {"name": "Weekly", "url": "https://www.merriam-webster.com/games/quordle/#/weekly"},
]

# Global variables (ported from quordleSolver.py)
allWords = wordListsMethods.getAllWords()
indivWords = [wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords()]
guessWord = ""
winsList = []
numLosses = 0
iteration = -1
squares = []
lastWordGuessedFromList = -1
lettersUsed = [1] * 26
avgLikelihoods = wordListsMethods.totalLetterLikelihoods(wordListsMethods.getLetterLikelihoods(allWords))
knowledgeList = [[""] * 5 for _ in range(4)]
resultsList = [[""] * 5 for _ in range(4)]

# Helper Functions

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

def findBestWord(active_board_idx=None):
    # Determine the range of boards to consider
    # If active_board_idx is specified, we ONLY look at that board (Sequence Mode)
    # Otherwise we look at all 4 (Classic Mode)
    board_range = range(4)
    if active_board_idx is not None:
        board_range = [active_board_idx]

    for i in board_range:
        if len(indivWords[i]) == 1:
            resultsList[i] = ["C", "C", "C", "C", "C"]
            print("Found word: ", indivWords[i][0], " --- Iteration: ", iteration + 1)
            return indivWords[i][0]

    combinedWordsList = []
    wordsLeft = 0
    for i in board_range:
        if knowledgeList[i] == ["D", "D", "D", "D", "D"]:
            wordsLeft += 1

    for i in board_range:
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
    
    # ... rest of function ...
    
    # Handle empty word list case - return None to signal game over
    if len(combinedWordsList) == 0:
        print("WARNING: No words left in combined list - cannot continue")
        return None

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
    
    if len(wordValueList) == 0:
        return None
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
                                if wordListCopy[j] in indivWords[word]:
                                    indivWords[word].remove(wordListCopy[j])
                else:
                    for i in range(len(wordListCopy)):
                        if wordListsMethods.wordContains(wordListCopy[i], lastWord[letter]):
                            if wordListCopy[i] in indivWords[word]:
                                indivWords[word].remove(wordListCopy[i])
            elif resultsList[word][letter] == "M":
                for i in range(len(wordListCopy)):
                    if wordListCopy[i][letter] == lastWord[letter]:
                        if wordListCopy[i] in indivWords[word]:
                            indivWords[word].remove(wordListCopy[i])
                        continue
                    if not wordListsMethods.wordContains(wordListCopy[i], lastWord[letter]):
                        if wordListCopy[i] in indivWords[word]:
                            indivWords[word].remove(wordListCopy[i])
            elif resultsList[word][letter] == "C":
                for i in range(len(wordListCopy)):
                    if wordListCopy[i][letter] != lastWord[letter]:
                        if wordListCopy[i] in indivWords[word]:
                            indivWords[word].remove(wordListCopy[i])
            else:
                # "Ignore" or empty state - do nothing
                pass

def reset_solver_state():
    """Reset all solver state variables for a new game mode."""
    global indivWords, resultsList, knowledgeList, lettersUsed, iteration, guessWord, lastWordGuessedFromList
    indivWords = [wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords()]
    resultsList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
    knowledgeList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
    lettersUsed = [1] * 26
    iteration = -1
    guessWord = ""
    lastWordGuessedFromList = -1

# Async functions for Playwright

async def get_square_color(page, i_idx, j_idx, row_idx, k_idx):
    xpath = f'//*[@id="game-board-row-{i_idx}"]/div[{j_idx}]/div[{row_idx}]/div[{k_idx}]'
    try:
        color = await page.locator(xpath).evaluate("e => getComputedStyle(e).backgroundColor")
        print(f"DEBUG: {xpath} -> {color}")
        return color
    except Exception as e:
        # print(f"Error getting color for {xpath}: {e}")
        return "rgba(0, 0, 0, 0)"

async def get_square_letter(page, i_idx, j_idx, row_idx, k_idx):
    """Get the letter inside a specific square."""
    xpath = f'//*[@id="game-board-row-{i_idx}"]/div[{j_idx}]/div[{row_idx}]/div[{k_idx}]'
    try:
        # Try getting text content directly or from aria-label
        letter = await page.locator(xpath).inner_text()
        return letter.strip().upper()
    except Exception as e:
        return ""

async def sync_sequence_board_state(page, active_board_idx):
    """
    Called when Sequence mode moves to a new board (e.g. 1 -> 2).
    We must re-read all previous guesses (lines 1 to iteration)
    and update the `indivWords` for THIS board using its revealed colors.
    """
    global iteration, guessWord, resultsList
    
    print(f"Syncing state for Board {active_board_idx+1} (History Catch-up)...")
    
    # Map active_board_idx (0..3) to sequence coordinates (1..2, 1..2)
    # 0->(1,1), 1->(1,2), 2->(2,1), 3->(2,2)
    coords = [(1, 1), (1, 2), (2, 1), (2, 2)]
    i_idx, j_idx = coords[active_board_idx]
    
    # `iteration` is 0-indexed count of guesses made so far.
    # So we have rows 1 to `iteration+1` filled.
    # Actually `iteration` increments AFTER a guess.
    # If we just finished guess 5 (iteration=5), we want to read rows 1..5?
    # No, iteration starts at -1. After 1 guess, iteration=0.
    # So we read rows 1 to `iteration + 1`.
    
    saved_guess_word = guessWord # Backup
    
    for row in range(1, iteration + 2):
        # 1. Get the word guessed in this row (from Board 1, as all are same)
        current_word = ""
        for k in range(1, 6):
            l = await get_square_letter(page, 1, 1, row, k)
            current_word += l
        
        if len(current_word) != 5:
             # Should not happen unless sync issue
            continue

        guessWord = current_word
        
        # 2. Get colors for the ACTIVE board at this row
        # We manually update resultsList[active_board_idx]
        for k in range(1, 6):
            color = await get_square_color(page, i_idx, j_idx, row, k)
            
            if "0, 204, 136" in color:
                resultsList[active_board_idx][k-1] = "C"
            elif "255, 204, 0" in color:
                resultsList[active_board_idx][k-1] = "M"
            elif "228, 228, 231" in color or "206, 213, 222" in color or "205, 213, 223" in color:
                resultsList[active_board_idx][k-1] = "I"
            else:
                # Treat others as I or ignore?
                # If sequence mode hidden previously, it might be gray now?
                # No, now it should be colored.
                resultsList[active_board_idx][k-1] = "I" # Assume incorrect if not green/yellow

        # 3. Apply filter
        # We only want to affect `indivWords[active_board_idx]`.
        # `removeWords()` affects ALL boards based on `resultsList`.
        # To be safe, we should ONLY touch `indivWords[active_board_idx]`.
        # But `removeWords` is hardcoded to loop 0..3.
        # However, `resultsList` for other boards should rely on their CURRENT state.
        # But we haven't updated `resultsList` for *other* boards for this *past* row.
        # Actually `resultsList` stores the *latest* feedback.
        # If we run `removeWords` now with `guessWord="PAST_GUESS"`, 
        # it will check `resultsList` for ALL boards.
        # `resultsList` for Board 0 is likely "Green/Solved" (since we passed it).
        # `resultsList` for Board 2/3 is empty/inactive.
        # So `removeWords` should naturally skip them (due to our Fix #1).
        # So it IS safe to run `removeWords` globally!
        removeWords()
        
    guessWord = saved_guess_word # Restore
    print(f"Board {active_board_idx+1} synced. Candidates left: {len(indivWords[active_board_idx])}")

async def sync_board_state(page):
    """
    Scans the board for any pre-filled moves (like in Rescue mode).
    Updates the solver's internal state (indivWords, resultsList) to match the board.
    """
    global iteration, guessWord, resultsList
    
    print("Syncing board state...")
    
    # We check rows 1 through 9. If a row has letters, we process it.
    # In Rescue mode, usually rows 1 and 2 are filled.
    
    found_prefilled = False
    
    for row in range(1, 10):
        # Check if the first square of the first board has a letter
        # We check board 1 (i=1, j=1)
        first_letter = await get_square_letter(page, 1, 1, row, 1)
        
        if not first_letter:
            # If no letter, we've reached the empty part of the board
            # So the *previous* row was the last filled one
            iteration = row - 2 # 0-indexed iteration
            break
            
        print(f"Detected pre-filled row {row}: reading inputs...")
        found_prefilled = True
        
        # Construct the word from the first board (since all boards get same input)
        # Note: In Rescue, all boards have the same word guessed
        current_word = ""
        for k in range(1, 6):
            l = await get_square_letter(page, 1, 1, row, k)
            current_word += l
            
        print(f"Pre-filled word: {current_word}")
        guessWord = current_word
        
        # Now update state via changeResultsListAsync logic
        # We need to set the global iteration to match this row for changeResultsListAsync to work
        iteration = row - 1
        
        # Read colors for this row
        await changeResultsListAsync(page)
        
        # Apply solver logic
        setLettersAsUsed(guessWord)
        removeWords()
        
    if found_prefilled:
        print(f"Board sync complete. Resuming at iteration {iteration + 1}")
    else:
        print("No pre-filled rows detected.")


async def get_solved_words(page):
    """
    Scans the 4 boards to find the solved (Green) words.
    Returns a list of 4 words.
    """
    solved_words = []
    
    # Boards are arranged in a 2x2 grid logic (i=1..2, j=1..2)
    # But usually we just iterate 0..3 for our internal list.
    # We need to map linear index 0..3 to (row_group, col_group)
    # Board 0: i=1, j=1
    # Board 1: i=1, j=2
    # Board 2: i=2, j=1
    # Board 3: i=2, j=2
    
    board_coords = [(1, 1), (1, 2), (2, 1), (2, 2)]
    
    for b_idx, (i, j) in enumerate(board_coords):
        word_found = "UNKNOWN"
        
        # Scan all rows (1-9) for this board to find the Green one
        for r in range(1, 10):
            # Check color of first letter
            color = await get_square_color(page, i, j, r, 1)
            
            # If Green
            if "0, 204, 136" in color:
                # This is the winning row! Extract the word.
                w = ""
                for k in range(1, 6):
                    l = await get_square_letter(page, i, j, r, k)
                    w += l
                word_found = w
                break
        
        solved_words.append(word_found)
        
    return solved_words

async def changeResultsListAsync(page, active_board_idx=None):
    global resultsList
    global knowledgeList
    global iteration
    
    current_xpath_row = iteration + 1
    
    board_idx = 0
    for i in range(1, 3):
        for j in range(1, 3):
            # If in Sequence mode, SKIP boards that are not the active one
            if active_board_idx is not None and board_idx != active_board_idx:
                board_idx += 1
                continue

            for k in range(1, 6):
                color = await get_square_color(page, i, j, current_xpath_row, k)
                
                if "0, 204, 136" in color:  # Green
                    resultsList[board_idx][k-1] = "C"
                    knowledgeList[board_idx][k-1] = "D"
                elif "255, 204, 0" in color:  # Yellow
                    resultsList[board_idx][k-1] = "M"
                elif "228, 228, 231" in color:  # Gray (incorrect)
                    resultsList[board_idx][k-1] = "I"
                elif "212, 212, 216" in color:  # Gray variant (Rescue mode)
                    resultsList[board_idx][k-1] = "I"
                elif "226, 232, 240" in color:  # Gray variant (Sequence/inactive board)
                    pass  # Inactive board, skip
                elif "244, 244, 245" in color:  # Already solved
                    pass
                elif "206, 213, 222" in color or "205, 213, 223" in color or "204, 213, 224" in color or "203, 213, 225" in color:  # Gray variants
                    resultsList[board_idx][k-1] = "I"
                else:
                    # In Rescue/Sequence mode, undefined colors might appear for hidden boards.
                    pass
            board_idx += 1

async def block_ads(route):
    url = route.request.url
    if any(x in url for x in ["googlesyndication", "doubleclick", "ads", "adnxs", "moatads"]):
        await route.abort()
    else:
        await route.continue_()

async def dismiss_popups(page):
    """Dismiss any popups that may appear (close buttons, modals, etc.)."""
    # Try to close the modal popup with X button
    close_selectors = [
        'button[aria-label="Close"]',
        'button:has(svg path[d*="M6 18L18 6"])',
        '.bg-white.rounded-full button',
        'button:has(title:text("Close"))',
    ]
    
    for selector in close_selectors:
        try:
            close_btn = page.locator(selector).first
            if await close_btn.is_visible(timeout=2000):
                print(f"Found popup close button: {selector}")
                await close_btn.click()
                await asyncio.sleep(1)
                print("Popup closed")
                break
        except:
            pass
    
    # Also click outside to dismiss any overlays
    await page.mouse.click(10, 10)
    await asyncio.sleep(0.5)

async def show_transition_screen(page, mode_name):
    """Display a beautiful transition screen with the mode name."""
    transition_html = f'''
    (function() {{
        var overlay = document.createElement('div');
        overlay.id = 'mode-transition-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 999999;
            animation: fadeIn 0.5s ease-out;
        `;
        
        var label = document.createElement('div');
        label.style.cssText = `
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 24px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 8px;
            margin-bottom: 20px;
        `;
        label.textContent = 'NOW SOLVING';
        
        var modeName = document.createElement('div');
        modeName.style.cssText = `
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 72px;
            font-weight: bold;
            color: #ffffff;
            text-transform: uppercase;
            letter-spacing: 12px;
            text-shadow: 0 0 40px rgba(255, 255, 255, 0.3);
            animation: pulse 2s infinite;
        `;
        modeName.textContent = '{mode_name}';
        
        var line = document.createElement('div');
        line.style.cssText = `
            width: 200px;
            height: 4px;
            background: linear-gradient(90deg, transparent, #00cc88, transparent);
            margin-top: 30px;
            border-radius: 2px;
        `;
        
        var style = document.createElement('style');
        style.textContent = `
            @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
            @keyframes pulse {{ 0%, 100% {{ transform: scale(1); }} 50% {{ transform: scale(1.02); }} }}
            @keyframes fadeOut {{ from {{ opacity: 1; }} to {{ opacity: 0; }} }}
        `;
        document.head.appendChild(style);
        
        overlay.appendChild(label);
        overlay.appendChild(modeName);
        overlay.appendChild(line);
        document.body.appendChild(overlay);
    }})();
    '''
    await page.evaluate(transition_html)
    await asyncio.sleep(3)
    
    await page.evaluate('''
    (function() {
        var overlay = document.getElementById('mode-transition-overlay');
        if (overlay) {
            overlay.style.animation = 'fadeOut 0.5s ease-out';
            setTimeout(function() { overlay.remove(); }, 500);
        }
    })();
    ''')
    await asyncio.sleep(0.5)

async def check_game_over(page):
    """Check if the game has ended (win or loss message visible)."""
    game_over_selectors = [
        'text="So close!"',
        'text="Nice work!"',
        'text="Brilliant!"',
        'text="Genius!"',
        'text="Impressive!"',
        'text="Great!"',
        'text="Phew!"',
    ]
    
    for selector in game_over_selectors:
        try:
            if await page.locator(selector).is_visible(timeout=500):
                return True
        except:
            pass
    return False

# ----- FALLBACK LOGIC -----

async def extract_answers_from_page(page):
    """
    Extracts the daily game data from the page source as a last resort.
    Searches for variables like Zi (Weekly List), A1, E1, using patterns in extract_words.py
    """
    try:
        content = await page.content()
        
        # Regex to find array-like structures
        # Zi = [[...], [...]]  <- This is the weekly list for standard/daily modes
        zi_match = re.search(r'[, ]Zi\s*=\s*(\[\[.*?\]\])', content, re.DOTALL)
        
        if not zi_match:
            print("Standard Zi extraction failed. Creating fallback list from regex patterns...")
            # Pattern 1: A1 = [...] or E1 = [...] (Common in specific game modes)
            # Pattern 2: Arrays of 5-letter uppercase words
            
            potential_arrays = []
            
            # Check for A1/E1 explicitly as requested
            a1_match = re.search(r'[, ]A1\s*=\s*(\[.*?\])', content, re.DOTALL)
            if a1_match:
                try:
                    # Often these answers are obfuscated or raw string lists.
                    # We might need to scrub comments/junk if raw JS.
                    clean_json = re.sub(r'/\*.*?\*/', '', a1_match.group(1))
                    potential_arrays.append(json.loads(clean_json))
                except: pass

            e1_match = re.search(r'const E1\s*=\s*(\[.*?\])', content, re.DOTALL)
            if e1_match:
                try:
                    clean_json = re.sub(r'/\*.*?\*/', '', e1_match.group(1))
                    potential_arrays.append(json.loads(clean_json))
                except: pass

            # General fallback: arrays of 4 words
            regex_arrays = re.findall(r'\["[A-Z]{5}","[A-Z]{5}","[A-Z]{5}","[A-Z]{5}"\]', content)
            for arr_str in regex_arrays:
                try:
                    potential_arrays.append(json.loads(arr_str))
                except: pass
                
            if potential_arrays:
                print(f"Found {len(potential_arrays)} potential answer arrays.")
                return potential_arrays
            
            return []

        # Parse the JSON found in Zi
        zi_str = zi_match.group(1)
        weekly_list = json.loads(zi_str)
        # weekly_list is usually an array of arrays of 4 words: [["WORD1", "WORD2", "WORD3", "WORD4"], ...]
        return weekly_list

    except Exception as e:
        print(f"Fallback extraction failed: {e}")
        return []

def fallback_solver(potential_answers_list):
    """
    Given a list of potential answer sets (e.g. from the parsed JS),
    find the one that matches our current known greens/yellows.
    Returns the next best word to guess from that answer set.
    """
    global knowledgeList, indivWords, resultsList
    
    print("Running fallback solver logic...")
    
    # We need to find which of the answer sets matches our current board state.
    # We iterate through each answer set in the list.
    
    matching_answers = None
    
    for answers in potential_answers_list:
        if len(answers) != 4:
            continue
            
        is_match = True
        
        # Check against each board
        for i in range(4):
            # If 'answers[i]' conflicts with what we know, it's not the right set.
            # We check if it is in indivWords[i]
            # UNLESS indivWords[i] is empty because we solved it.
            
            if len(indivWords[i]) == 0:
                # Board solved.
                pass
            else:
                if answers[i] not in indivWords[i]:
                    is_match = False
                    break
        
        if is_match:
            matching_answers = answers
            break
    
    if not matching_answers:
        print("Fallback: Could not find a matching answer set in the extracted data.")
        # Desperate Fallback: Just maximize overlap with remaining candidate lists
        # If we failed to match, maybe we just pick the first valid word from the first board that is unsolved?
        for i in range(4):
            if len(indivWords[i]) > 0:
                return indivWords[i][0]
        return None

    print(f"Fallback: Found matching answers: {matching_answers}")
    
    # Return the first unsolved word from the answer set
    for i in range(4):
        if len(indivWords[i]) > 0: # This board is not solved
             return matching_answers[i]
             
    return None

async def show_victory_screen(page, mode_name, solved_words):
    """Display a beautiful victory screen with the solved words."""
    words_html = ""
    for w in solved_words:
        words_html += f'<div style="font-size: 40px; margin: 10px; color: #4ade80; text-shadow: 0 0 10px rgba(74, 222, 128, 0.5);">{w}</div>'
        
    overlay_html = f'''
    (function() {{
        var overlay = document.createElement('div');
        overlay.id = 'victory-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(15, 23, 42, 0.95);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 999999;
            opacity: 0;
            transition: opacity 1s ease-in;
        `;
        
        var title = document.createElement('div');
        title.innerHTML = '{mode_name} <span style="color: #facc15">SOLVED</span>';
        title.style.cssText = `
            font-family: 'Segoe UI', sans-serif;
            font-size: 60px;
            font-weight: bold;
            color: white;
            margin-bottom: 40px;
            text-transform: uppercase;
            letter-spacing: 4px;
        `;
        
        var wordsContainer = document.createElement('div');
        wordsContainer.style.cssText = `
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            max-width: 800px;
        `;
        wordsContainer.innerHTML = `{words_html}`;
        
        overlay.appendChild(title);
        overlay.appendChild(wordsContainer);
        document.body.appendChild(overlay);
        
        // Trigger fade in
        setTimeout(() => {{ overlay.style.opacity = '1'; }}, 100);
    }})();
    '''
    await page.evaluate(overlay_html)
    await asyncio.sleep(5) # Show for 5 seconds
    
    # Fade out
    await page.evaluate('''
        var ov = document.getElementById('victory-overlay');
        if(ov) {
            ov.style.transition = 'opacity 0.5s ease-out';
            ov.style.opacity = '0';
            setTimeout(() => ov.remove(), 500);
        }
    ''')


async def play_single_mode(page, mode_name):
    """Play a single Quordle game mode."""
    global guessWord
    global lastWordGuessedFromList
    global iteration
    global winsList
    global numLosses
    global indivWords
    global resultsList
    global knowledgeList
    global lettersUsed
    
    print(f"\n{'='*50}")
    print(f"Starting {mode_name} mode...")
    print(f"{'='*50}\n")
    
    reset_solver_state()
    
    is_sequence = "Sequence" in mode_name
    
    # 1. Sync board state (CRITICAL for Rescue mode)
    await sync_board_state(page)
    
    # Quordle allows 9 guesses max (Sequence usually has more, but let's see)
    # Actually Sequence allows 10 guesses? No, 9.
    # Wait, Sequence allows 10 guesses? Let's assume standard 9 for now, maybe more.
    # Checking online: Sequence mode gives 10 guesses.
    max_guesses = 10 if is_sequence else 9
    
    start_guess = iteration + 1
    
    solved_words_final = []
    
    for i in range(start_guess, max_guesses):
        # Check if game already ended
        if await check_game_over(page):
            print(f"{mode_name}: Game already ended")
            break
        
        # SEQUENCE MODE SPECIFIC LOGIC
        active_board_idx = None
        if is_sequence:
            # Boards are solved in order 0, 1, 2, 3
            current_board_index = 0
            for b_idx in range(4):
                # We need to rely on `resultsList` state (["C","C","C","C","C"]) for solved status
                if resultsList[b_idx] == ["C", "C", "C", "C", "C"]:
                    current_board_index = b_idx + 1
                else:
                    # If this board is NOT solved, it is the current one
                    break
            
            # If current_board_index is 4, we won (loop will handle it in check_game_over logic usually, but here specific check)
            if current_board_index > 3:
                current_board_index = 3 # Cap at 3 purely for safety, though we likely broke out already

            # Check if we switched boards implies we need to Resync history for new board
            # We track `last_active_board_idx` (need to init it outside loop)
            if 'last_active_board_idx' not in locals():
                last_active_board_idx = 0
            
            if current_board_index > last_active_board_idx:
                # We just advanced to a new board!
                # We need to sync its history
                await sync_sequence_board_state(page, current_board_index)
                last_active_board_idx = current_board_index
            
            active_board_idx = current_board_index
            
            # CRITICAL: For Sequence mode, we MUST keep `indivWords` for FUTURE boards generic/full.
            # `removeWords` will try to filter them based on `resultsList`.
            # If `resultsList` for a hidden board is empty (initial state), `removeWords` does nothing to it.
            # This is good! We just need `changeResultsListAsync` to NOT pollute `resultsList` with "Incorrect".
            pass

        # 3-STRIKE RULE: specific optimization for Sequence Mode Board 1
        # If we are on Board 1 (idx 0) and we have made 3 or more guesses (i-start_guess >= 3), 
        # and it's still not solved, force a fallback cheat.
        if is_sequence and active_board_idx == 0 and (i - start_guess) >= 3:
            print(f"Sequence Board 1 Taking too long ({i - start_guess} guesses). Triggering 3-Strike Fallback...")
            potential_answers = await extract_answers_from_page(page)
            guessWord = fallback_solver(potential_answers)
            
            if guessWord:
                 print(f"3-Strike Rescue: Suggesting {guessWord}")
            else:
                 print("3-Strike Rescue failed to find word. Continuing normal solver.")
                 guessWord = findBestWord(active_board_idx=active_board_idx)
        else:
            guessWord = findBestWord(active_board_idx=active_board_idx)
        
        # 3. Fallback Mechanism
        if guessWord is None:
            print(f"{mode_name}: Standard solver stuck. Attempting fallback extraction...")
            potential_answers = await extract_answers_from_page(page)
            guessWord = fallback_solver(potential_answers)
            
            if guessWord:
                print(f"Fallback Strategy: Suggesting {guessWord}")
            else:
                print(f"{mode_name}: No valid word found including fallback - ending mode")
                numLosses += 1
                break
        
        setLettersAsUsed(guessWord)
        
        # Track where this word came from (logic from original solver)
        for idx in range(4):
            for w in indivWords[idx]:
                if guessWord == w:
                    lastWordGuessedFromList = idx
        
        print(f"[{mode_name}] Guessing ({i+1}/{max_guesses}): {guessWord}")
        
        # Type slowly to avoid issues
        await page.keyboard.type(guessWord, delay=100)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3)
        
        # Check if game ended after this guess
        if await check_game_over(page):
            # Check if we won (all boards green)
            if resultsList == [["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"]]:
                winsList.append(i+1)
                print(f"{mode_name}: WIN in {i+1} guesses!")
                
                print("Extracting solved words for victory screen...")
                final_words = await get_solved_words(page)
                # If extraction failed for some reason, fallback
                if not final_words or "UNKNOWN" in final_words:
                    # fallback to previous logic or just show what we have
                    pass
                
                await show_victory_screen(page, mode_name, final_words) 
            else:
                numLosses += 1
                print(f"{mode_name}: LOSS (So close!)")
            break
        
        iteration += 1
        await changeResultsListAsync(page, active_board_idx=active_board_idx)
        removeWords()
        
        # Check for win via internal state
        if resultsList == [["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"]]:
            winsList.append(i+1)
            print(f"{mode_name}: WIN in {i+1} guesses!")
            
            final_words = await get_solved_words(page)
            await show_victory_screen(page, mode_name, final_words)
            break
    
    await asyncio.sleep(2)


async def play_mode_in_existing_context(page, mode, mode_idx):
    """Play a mode using the existing page/context (preserves cookies)."""
    mode_name = mode["name"]
    mode_url = mode["url"]
    
    print(f"\n{'#'*60}")
    print(f"# Mode {mode_idx + 1}/{len(GAME_MODES)}: {mode_name}")
    print(f"# URL: {mode_url}")
    print(f"{'#'*60}\n")
    
    # Navigate to mode
    try:
        await page.goto(mode_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"Navigation warning for {mode_name}: {e}")
    
    # Wait for game board
    try:
        await page.wait_for_selector('//*[@id="game-board-row-1"]', timeout=30000)
    except:
        print(f"Timeout waiting for game board in {mode_name}")
    
    # Wait for page to fully load
    await asyncio.sleep(2)
    
    # Dismiss any popups
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    # Show transition screen
    await show_transition_screen(page, mode_name)
    
    # Play the mode
    await play_single_mode(page, mode_name)


async def main():
    global winsList
    global numLosses
    
    script_dir = Path(__file__).parent
    video_dir = script_dir / "videos"
    video_dir.mkdir(exist_ok=True)
    
    mode_videos = []
    
    async with async_playwright() as p:
        print(f"Starting browser (headless={HEADLESS})...")
        browser = await p.chromium.launch(headless=HEADLESS)
        
        # Create ONE persistent context for all modes
        context = await browser.new_context(
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        await context.route("**/*", block_ads)
        page = await context.new_page()
        
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Play each mode in order
        for mode_idx, mode in enumerate(GAME_MODES):
            await play_mode_in_existing_context(page, mode, mode_idx)
            # Note: We are recording one GIANT video now, not separate ones.
            # OR we can try to split them?
            # Playwright video recording is per-page.
            # If we reuse the page, we get one long video.
            # This is actually better for "Sequence" flow, but we might want chapters.
            # But the user asked for one video at the end anyway.
            # So one long video is fine.
        
        # Get video path
        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        if video_path:
             mode_videos.append(video_path)
    
    # Post-game summary
    print(f"\n{'='*60}")
    print(f"ALL MODES COMPLETED!")
    print(f"Total Wins: {len(winsList)} - Total Losses: {numLosses}")
    print(f"{'='*60}\n")
    
    # Rename/Process the single video file
    final_video_path = mode_videos[0] if mode_videos else None
    
    # Add background music
    if final_video_path:
        final_video_path = add_background_music(final_video_path, script_dir, video_dir)
    
    # Upload to YouTube
    if YOUTUBE_AVAILABLE and final_video_path:
        today = datetime.now().strftime("%B %d, %Y")
        title = f"Quordle {today} - All Modes Solved! (Classic, Chill, Extreme, Rescue, Sequence, Weekly)"
        upload_to_youtube(str(final_video_path), title=title)
    else:
        print("Skipping YouTube upload.")
    
    print("Done!")


def concatenate_videos(video_paths, script_dir, video_dir):
    """Concatenate multiple videos into one using ffmpeg."""
    if not video_paths:
        return None
    
    # Create a file list for ffmpeg
    list_file = video_dir / "video_list.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            # Escape path for ffmpeg
            escaped_path = str(vp).replace("\\", "/")
            f.write(f"file '{escaped_path}'\n")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = video_dir / f"quordle_combined_{timestamp}.mp4"
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    
    try:
        print("Concatenating mode videos...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"Combined video: {output_path}")
            # Clean up individual videos
            for vp in video_paths:
                try:
                    Path(vp).unlink()
                except:
                    pass
            try:
                list_file.unlink()
            except:
                pass
            return output_path
        else:
            print(f"ffmpeg concat error: {result.stderr}")
            return Path(video_paths[0]) if video_paths else None
    except FileNotFoundError:
        print("ffmpeg not found.")
        return Path(video_paths[0]) if video_paths else None
    except subprocess.TimeoutExpired:
        print("ffmpeg concat timed out.")
        return Path(video_paths[0]) if video_paths else None


def add_background_music(video_path, script_dir, video_dir):
    """Add random background music to the video using ffmpeg."""
    song_name = random.choice(SONGS)
    song_path = script_dir / song_name
    
    if not song_path.exists():
        print(f"Song not found: {song_path}. Skipping music.")
        return video_path
    
    print(f"Adding background music: {song_name}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = video_dir / f"quordle_all_modes_{timestamp}.mp4"
    
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
            try:
                Path(video_path).unlink()
            except:
                pass
            return output_path
        else:
            print(f"ffmpeg error: {result.stderr}")
            return video_path
    except FileNotFoundError:
        print("ffmpeg not found.")
        return video_path
    except subprocess.TimeoutExpired:
        print("ffmpeg timed out.")
        return video_path


if __name__ == "__main__":
    asyncio.run(main())
