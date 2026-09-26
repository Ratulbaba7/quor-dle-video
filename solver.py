import asyncio
import os
import subprocess
import random
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import re
import json
import requests
import wordListsMethods
import quordle_answers_local
from quordle_thumbnail import generate_quordle_thumbnail
import quordle_parity as QP

# Import YouTube upload (optional - graceful if missing)
try:
    from youtube_upload import upload_to_youtube
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    print("YouTube upload module not available.")

# moviepy optional (Wordle-style assembly); ffmpeg fallback otherwise
try:
    from moviepy.editor import VideoFileClip, ImageClip, concatenate_videoclips, AudioFileClip
    import moviepy.audio.fx.all as afx
    MOVIEPY_AVAILABLE = True
except Exception:
    MOVIEPY_AVAILABLE = False

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
_last_row = {}

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
    global indivWords, resultsList, knowledgeList, lettersUsed, iteration, guessWord, lastWordGuessedFromList, _last_row
    indivWords = [wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords(), wordListsMethods.getAllWords()]
    resultsList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
    knowledgeList = [["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""], ["", "", "", "", ""]]
    lettersUsed = [1] * 26
    iteration = -1
    guessWord = ""
    lastWordGuessedFromList = -1
    _last_row = {}

# Async functions for Playwright

# ---------------------------------------------------------------- board reading
# New MW markup (Sep 2026): div[aria-label="Game Board N"] > .quordle-guess-row
# (5x .quordle-box). Tile aria-label verbs: "is correct" (C, bg-box-correct),
# "is in a different spot" (M, bg-box-diff), "is incorrect" (I, bg-zinc-200),
# "being guessed"/"a future guess"/"invalid guess" (not submitted yet).
# All reads go through page.evaluate — locator.count()/is_visible() are
# unreliable here.

async def _safe_eval(page, js, default=None):
    try:
        return await page.evaluate(js)
    except Exception:
        return default


def _aria_state(aria):
    aria = aria or ""
    if "different spot" in aria:
        return "M"
    if "incorrect" in aria:
        return "I"
    if "correct" in aria:
        return "C"
    return None


READ_ROW_JS = """(payload) => {
    const boards = document.querySelectorAll('div[aria-label="Game Board ' + payload.board + '"]');
    if (!boards.length) return null;
    const rows = boards[0].querySelectorAll('.quordle-guess-row');
    if (payload.row >= rows.length) return null;
    const tiles = rows[payload.row].querySelectorAll('.quordle-box');
    const out = [];
    tiles.forEach(t => out.push({
        letter: (t.innerText || '').trim().toUpperCase(),
        aria: t.getAttribute('aria-label') || ''
    }));
    return out;
}"""


async def read_board_row(page, board_idx, row_idx):
    """Return (word, [C/M/I...]) for a board row; unsubmitted tiles -> (word, None)."""
    try:
        tiles = await page.evaluate(READ_ROW_JS, {"board": board_idx + 1, "row": row_idx})
    except Exception:
        return None, None
    if not tiles or len(tiles) != 5:
        return None, None
    word = "".join(t.get("letter", "") for t in tiles)
    if len(word) != 5:
        return None, None
    states = [_aria_state(t.get("aria", "")) for t in tiles]
    if any(s is None for s in states):
        return word, None
    return word, states


async def read_latest_row(page, board_idx, max_rows=12):
    """Latest submitted row for a board: (row_idx, word, states) or (None...)."""
    start = _last_row.get(board_idx, 0)
    found = None
    for r in range(start, max_rows):
        word, states = await read_board_row(page, board_idx, r)
        if word and states:
            found = (r, word, states)
            _last_row[board_idx] = r
        elif word and not states:
            break
    if found:
        return found
    # fall back to full scan (board may have reset underneath us)
    _last_row[board_idx] = 0
    for r in range(max_rows):
        word, states = await read_board_row(page, board_idx, r)
        if word and states:
            found = (r, word, states)
            _last_row[board_idx] = r
        elif word and not states:
            break
    if found:
        return found
    return None, None, None


async def wait_for_game(page, timeout_s=45):
    """Wait until the board is mounted (keys + at least one guess row)."""
    for _ in range(int(timeout_s * 2)):
        n = await _safe_eval(page, "() => document.querySelectorAll('.quordle-key').length", 0) or 0
        rows = await _safe_eval(page, "() => document.querySelectorAll('.quordle-guess-row').length", 0) or 0
        if n >= 20 and rows > 0:
            return True
        await page.wait_for_timeout(500)
    return False


async def dismiss_welcome(page):
    """Close a welcome / instructions dialog if one is up."""
    clicked = await _safe_eval(
        page,
        """() => {
            const dlg = document.querySelector('[role="dialog"]');
            if (!dlg) return 'none';
            const btns = Array.from(dlg.querySelectorAll('button,a'));
            const want = btns.find(b => /got it|play|start|continue|close|let.s go/i.test(b.innerText || ''));
            (want || btns[0] || {click:()=>{}}).click();
            return want ? 'clicked:' + (want.innerText || '').slice(0, 20) : (btns.length ? 'clicked-first' : 'no-btn');
        }""",
        "eval-fail",
    )
    print(f"[quordle] welcome overlay: {clicked}")
    await page.wait_for_timeout(1500)


async def probe_live(page, timeout_s=60):
    """Type/clear a letter to prove the board accepts input. Returns bool.

    Reads the whole Board 1 text before/after (Rescue starts on later
    rows, so row 0 alone is not a valid probe target).
    """
    board_text_js = """() => { const b = document.querySelector('div[aria-label="Game Board 1"]'); return b ? b.innerText : ''; }"""
    for _ in range(int(timeout_s / 4)):
        try:
            before = await _safe_eval(page, board_text_js, "")
            await page.keyboard.type("q", delay=60)
            await page.wait_for_timeout(1200)
            after = await _safe_eval(page, board_text_js, "")
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(800)
            if after and after != (before or "") and "Q" in after.upper():
                # confirm the probe letter is fully cleared (else it would
                # corrupt the first real guess); retry Backspace a few times.
                for _ in range(3):
                    cur = await _safe_eval(page, board_text_js, "")
                    if cur == (before or ""):
                        break
                    await page.keyboard.press("Backspace")
                    await page.wait_for_timeout(500)
                return True
        except Exception:
            pass
        await page.wait_for_timeout(1500)
    return False


async def sync_sequence_board_state(page, active_board_idx, max_rows=10):
    """
    Called when Sequence mode moves to a new board (e.g. 1 -> 2).
    Re-read all previous guesses and update state for THIS board using its
    revealed aria-label states.
    """
    global iteration, guessWord, resultsList, knowledgeList

    print(f"Syncing state for Board {active_board_idx + 1} (History Catch-up)...")
    saved_guess_word = guessWord  # Backup
    for row in range(0, iteration + 1):
        word, states = await read_board_row(page, active_board_idx, row)
        if not word or not states:
            continue
        guessWord = word
        resultsList[active_board_idx] = list(states)
        for k, s in enumerate(states):
            if s == "C":
                knowledgeList[active_board_idx][k] = "D"
        removeWords()
    guessWord = saved_guess_word  # Restore
    print(f"Board {active_board_idx + 1} synced. Candidates left: {len(indivWords[active_board_idx])}")


async def sync_board_state(page, max_rows=12):
    """
    Replay any pre-filled rows (like in Rescue mode) into solver state,
    reading the current markup via aria-label.

    Rescue mode starts with several pre-filled guess rows: the SAME physical
    guess appears on all 4 boards, each board showing its own per-board
    feedback colors. Every pre-filled row must be applied per-board at the
    SAME row index. Previously this called changeResultsListAsync (which reads
    the LATEST submitted row per board), so while replaying row r it applied
    feedback from a different row -> word/feedback mismatch -> removeWords()
    pruned every candidate. We now inline a per-board, per-row read instead.
    """
    global iteration, guessWord, resultsList, knowledgeList

    print("Syncing board state...")
    found_prefilled = False
    for row in range(max_rows):
        # Use board 0 to detect end-of-prefill and get the row's guess word.
        b0_word, b0_states = await read_board_row(page, 0, row)

        # Determine the guess word for this row. Prefer board 0; if board 0
        # row r is unreadable, fall back to any board that returns 5 letters.
        row_word = b0_word if (b0_word and len(b0_word) == 5) else None
        if row_word is None:
            for b in range(1, 4):
                w, _ = await read_board_row(page, b, row)
                if w and len(w) == 5:
                    row_word = w
                    break

        # No word on any board for this row -> end of the pre-filled section.
        if not row_word:
            iteration = row - 1
            break

        # A row with a word but NO revealed states anywhere is the current
        # (unsubmitted) row; do not replay it.
        row_has_states = bool(b0_states)
        if not row_has_states:
            for b in range(1, 4):
                _, s = await read_board_row(page, b, row)
                if s:
                    row_has_states = True
                    break
        if not row_has_states:
            iteration = row - 1
            break

        print(f"Detected pre-filled row {row + 1}: {row_word}")
        found_prefilled = True

        # Apply this row's feedback per-board at the SAME row index. Read row r
        # on every board; only overwrite resultsList[b] when that board returns
        # valid states, otherwise leave its existing resultsList untouched.
        for b in range(4):
            word_b, states_b = await read_board_row(page, b, row)
            # Guard against desync/garbage: skip a board whose row is
            # unreadable or has bad length rather than corrupting state.
            if not states_b:
                continue
            if not word_b or len(word_b) != 5 or len(states_b) != 5:
                continue
            resultsList[b] = list(states_b)
            for k, s in enumerate(states_b):
                if s == "C":
                    knowledgeList[b][k] = "D"

        guessWord = row_word
        iteration = row
        setLettersAsUsed(guessWord)
        removeWords()

    if found_prefilled:
        print(f"Board sync complete. Resuming at iteration {iteration + 1}")
    else:
        print("No pre-filled rows detected.")


async def get_solved_words(page, max_rows=12):
    """
    Scan the 4 boards to find the solved (all-correct) words.
    Returns a list of 4 words.
    """
    solved_words = []
    for b in range(4):
        word_found = "UNKNOWN"
        for r in range(max_rows):
            word, states = await read_board_row(page, b, r)
            if word and states == ["C", "C", "C", "C", "C"]:
                word_found = word
                break
        solved_words.append(word_found)
    return solved_words


async def changeResultsListAsync(page, active_board_idx=None, max_rows=12):
    global resultsList, knowledgeList, iteration
    targets = range(4) if active_board_idx is None else [active_board_idx]
    for board_idx in targets:
        _, word, states = await read_latest_row(page, board_idx, max_rows)
        if not word or not states:
            continue
        resultsList[board_idx] = list(states)
        for k, s in enumerate(states):
            if s == "C":
                knowledgeList[board_idx][k] = "D"


async def resync_results_from_dom(page, max_rows=12):
    """
    Rebuild resultsList/knowledgeList from the latest submitted row on every
    board by re-reading the DOM. Used as a recovery step when the solver gets
    stuck (empty candidate list) so a single bad prune does not instantly lose.

    Forces a full re-scan (clears the _last_row cache) and guards against
    desync: a board whose latest row is unreadable or malformed is skipped
    rather than corrupting state.
    """
    global resultsList, knowledgeList, _last_row
    _last_row = {}
    for board_idx in range(4):
        _, word, states = await read_latest_row(page, board_idx, max_rows)
        if not word or not states:
            continue
        if len(word) != 5 or len(states) != 5:
            continue
        resultsList[board_idx] = list(states)
        for k, s in enumerate(states):
            if s == "C":
                knowledgeList[board_idx][k] = "D"

async def block_ads(route):
    url = route.request.url
    if any(x in url for x in ["googlesyndication", "doubleclick", "ads", "adnxs", "moatads"]):
        await route.abort()
    else:
        await route.continue_()

async def dismiss_popups(page):
    """Dismiss any popups that may appear (close buttons, modals, etc.)."""
    found = await _safe_eval(
        page,
        """() => {
            const sels = ['button[aria-label="Close"]', '.bg-white.rounded-full button'];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el && el.getBoundingClientRect().width > 0) { el.click(); return s; }
            }
            return null;
        }""",
    )
    if found:
        print(f"Popup closed: {found}")
        await page.wait_for_timeout(1000)
    # Also click outside to dismiss any overlays
    try:
        await page.mouse.click(10, 10)
    except Exception:
        pass
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
    phrases = ["So close!", "Nice work!", "Brilliant!", "Genius!", "Impressive!", "Great!", "Phew!", "Congrats!"]
    text = await _safe_eval(page, "() => document.body.innerText", "") or ""
    if any(p in text for p in phrases):
        return True
    # end screens sometimes render in a dialog that innerText windows miss
    dlg = await _safe_eval(
        page,
        """() => {
            const d = document.querySelector('[role="dialog"]');
            return d ? d.innerText.slice(0, 500) : '';
        }""",
        "",
    ) or ""
    return any(p in dlg for p in phrases)

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


# ---------------------------------------------------------------- official answers
# Wordle-style guarantee: we publish the correct daily answers on our own site,
# so after one organic show-guess we can green each board deterministically.
# The site data is SvelteKit devalue-encoded; resolve_devalue turns the
# index-addressed __data.json payload back into plain values.

OFFICIAL_MODE_KEY = {
    "Classic": "d", "Chill": "c", "Extreme": "e",
    "Sequence": "s", "Rescue": "r", "Weekly": "w",
}

_official_cache = {}


def resolve_devalue(data):
    """Resolve SvelteKit __data.json index references into plain values."""
    def _res(x):
        if isinstance(x, int) and 0 <= x < len(data):
            return _res(data[x])
        if isinstance(x, list):
            return [_res(v) for v in x]
        if isinstance(x, dict):
            return {k: _res(v) for k, v in x.items()}
        return x
    return _res(data)


def _target_quordle_date():
    """Calendar date the browser will be playing, from TZ_OFFSET_MINUTES.

    Mirrors the Playwright context timezone (BROWSER_TZ, default Asia/Tokyo):
    production uses 540 (UTC+9) so an evening-IST run targets the NEXT day.
    """
    from datetime import timedelta as _td
    try:
        off = int(os.environ.get("TZ_OFFSET_MINUTES", "540"))
    except ValueError:
        off = 540
    return datetime.utcnow() + _td(minutes=off)


def fetch_official_quordle():
    """Daily answers for the date the browser will play.

    PRIMARY: local deterministic generator (bit-exact port of our frontend's
    quordle.ts) -- works for ANY date incl. tomorrow, no network.
    CROSS-CHECK: frontend __data.json (today only); logs drift, never wins.
    Returns (dateKey, {modeName: [4 words]}). On total failure returns
    (None, {}) so the solver still runs (pure-solver fallback).
    """
    if "data" in _official_cache:
        return _official_cache["data"]
    try:
        target = _target_quordle_date()
        date_key = target.strftime("%Y-%m-%d")
        out = quordle_answers_local.get_quordle_for_date(target)
        out = {m: [w.upper() for w in ws] for m, ws in out.items()
               if len(ws) == 4 and all(len(w) == 5 for w in ws)}
        print(f"[official] LOCAL generator {date_key}: "
              + ", ".join(f"{m}={','.join(w)}" for m, w in out.items()))
        try:
            fe_date, fe_map = _fetch_official_from_frontend()
            if fe_date == date_key and fe_map:
                diffs = [m for m in fe_map if fe_map.get(m) != out.get(m)]
                if diffs:
                    print(f"[official] WARN frontend differs on {diffs} -> trusting LOCAL")
                else:
                    print("[official] frontend cross-check OK")
        except Exception:
            pass
        _official_cache["data"] = (date_key, out)
        return date_key, out
    except Exception as e:
        print(f"[official] local generator failed ({e}); trying frontend")
    return _fetch_official_from_frontend()


def _fetch_official_from_frontend():
    """Frontend __data.json answers (TODAY only) - cross-check/fallback."""
    try:
        r = requests.get(
            "https://wordsolverx.com/quordle-answer-today/__data.json",
            timeout=20,
            headers={"User-Agent": "WordSolverX Video", "Accept": "application/json"},
        )
        r.raise_for_status()
        payload = r.json()
        today_data = None
        date_key = None
        for node in payload.get("nodes", []):
            if not isinstance(node, dict) or node.get("type") != "data":
                continue
            resolved = resolve_devalue(node["data"])
            root = resolved[0] if isinstance(resolved, list) and resolved else resolved
            if isinstance(root, dict) and isinstance(root.get("todayData"), dict):
                today_data = root["todayData"]
                date_key = root.get("dateKey")
                break
        if not today_data:
            print("[official] todayData not found in __data.json")
            return None, {}
        out = {}
        for mode, key in OFFICIAL_MODE_KEY.items():
            words = [str(w).upper() for w in (today_data.get(key) or [])]
            if len(words) == 4 and all(len(w) == 5 for w in words):
                out[mode] = words
        print(f"[official] FRONTEND {date_key}: " + ", ".join(f"{m}={','.join(w)}" for m, w in out.items()))
        _official_cache["data"] = (date_key, out)
        return date_key, out
    except Exception as e:
        print(f"[official] fetch failed (solver fallback): {e}")
        return None, {}
async def play_single_mode(page, mode_name, official=None):
    """Play a single Quordle game mode.

    If `official` (the 4 daily answers for this mode) is provided, the solver
    plays one organic show-guess and then greens each board with the official
    answers (Wordle-style guarantee). A drift check hands control back to the
    pure solver if the site data is out of sync with the live board.
    """
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
    counted_boards = set()
    
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
    
    # Guided answers (Wordle-style guarantee): keep the FIRST organic guess so
    # the video shows real solving, then guess the official answer for the first
    # currently-unsolved board (board order = solve order, incl. Sequence).
    # Disabled on drift (solver takes over). Practice/Weekly or any mode with no
    # official entry -> guided stays off -> pure solver path (unchanged).
    guided = [(w or "").upper() for w in (official or []) if w]
    guided = [w for w in guided if len(w) == 5]
    guided_ok = len(guided) == 4
    used = set()
    guided_target = None
    if guided_ok:
        print(f"[{mode_name}] guided answers: {','.join(guided)}")
    
    last_active_board_idx = 0
    
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
        # (Skipped when guided answers are driving — the guarantee wins quickly.)
        if is_sequence and active_board_idx == 0 and (i - start_guess) >= 3 and not guided_ok:
            print(f"Sequence Board 1 Taking too long ({i - start_guess} guesses). Triggering 3-Strike Fallback...")
            potential_answers = await extract_answers_from_page(page)
            guessWord = fallback_solver(potential_answers)
            
            if guessWord:
                 print(f"3-Strike Rescue: Suggesting {guessWord}")
            else:
                 print("3-Strike Rescue failed to find word. Continuing normal solver.")
                 guessWord = findBestWord(active_board_idx=active_board_idx)
        elif guided_ok and used:
            # Guided path (after the first organic guess): pick the official
            # answer for the first currently-unsolved board that we have not
            # typed yet. In Sequence only the active board is fillable, and its
            # official answer is the right pick there too (board order matches
            # solve order). Greens boards deterministically -> win in a few.
            guided_target = None
            nxt = None
            board_scan = [active_board_idx] if (is_sequence and active_board_idx is not None) else range(4)
            for b_idx in board_scan:
                if resultsList[b_idx] != ["C", "C", "C", "C", "C"] and guided[b_idx] not in used:
                    nxt = guided[b_idx]
                    guided_target = b_idx
                    break
            if nxt is None:
                print(f"[{mode_name}] guided answers exhausted/ambiguous -> solver takes over")
                guided_ok = False
                guessWord = findBestWord(active_board_idx=active_board_idx)
            else:
                guessWord = nxt
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
                # Robustness: a single transient empty candidate list should not
                # instantly lose. Re-sync the visible board state from the DOM
                # (latest submitted row on every board) and retry findBestWord
                # once before recording a loss.
                print(f"{mode_name}: Fallback empty. Re-syncing board state from DOM and retrying...")
                await resync_results_from_dom(page)
                guessWord = findBestWord(active_board_idx=active_board_idx)

                if guessWord:
                    print(f"Recovery after re-sync: Suggesting {guessWord}")
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
        
        # Read the revealed feedback for this guess, then prune candidates.
        iteration += 1
        await changeResultsListAsync(page, active_board_idx=active_board_idx)
        removeWords()
        used.add((guessWord or "").upper())

        # per-board win tracking (verify gate counts 4 boards x 6 modes = 24)
        for bi in range(4):
            if (bi not in counted_boards
                    and resultsList[bi] == ["C", "C", "C", "C", "C"]):
                counted_boards.add(bi)
                winsList.append(bi + 1)
        
        # Drift check: a guided guess MUST green its targeted board. If it did
        # not (site data out of sync with the live board), hand control back to
        # the organic solver for the rest of this mode.
        if guided_ok and guided_target is not None:
            if resultsList[guided_target] != ["C", "C", "C", "C", "C"]:
                print(f"[{mode_name}] guided drift on board {guided_target + 1} -> solver takes over")
                guided_ok = False
            guided_target = None
        
        # Check for win via internal state (all four boards green)
        if resultsList == [["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"], ["C", "C", "C", "C", "C"]]:
            print(f"{mode_name}: WIN in {i+1} guesses!")
            
            final_words = await get_solved_words(page)
            await show_victory_screen(page, mode_name, final_words)
            break
        
        # Check if game ended after this guess without a win -> loss
        if await check_game_over(page):
            numLosses += 1
            print(f"{mode_name}: LOSS (So close!)")
            break
    
    await asyncio.sleep(2)


async def enter_mode(page, mode):
    """Navigate to a mode and wait until the board mounts. Returns bool."""
    mode_name = mode["name"]
    if mode_name == "Classic":
        # Daily classic has no direct route: use the menu Play anchor.
        try:
            await page.goto("https://www.merriam-webster.com/games/quordle/#/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Navigation warning for {mode_name}: {e}")
        await asyncio.sleep(6)
        try:
            await page.evaluate("() => { Array.from(document.querySelectorAll('a')).filter(a => a.innerText.trim() === 'Play')[0].click(); }")
        except Exception:
            pass  # click navigates -> context destroyed is expected
        if not await wait_for_game(page, timeout_s=20):
            print(f"{mode_name}: classic board never mounted, skipping")
            return False
        await dismiss_welcome(page)
        await dismiss_popups(page)
        if not await probe_live(page, timeout_s=30):
            print(f"{mode_name}: board not accepting input, skipping mode")
            return False
        return True
    try:
        await page.goto(mode["url"], wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"Navigation warning for {mode_name}: {e}")
    if not await wait_for_game(page, timeout_s=45):
        print(f"Timeout waiting for game board in {mode_name}")
        return False
    await dismiss_welcome(page)
    await dismiss_popups(page)
    if not await probe_live(page, timeout_s=60):
        print(f"{mode_name}: board not accepting input, skipping mode")
        return False
    return True


async def play_mode_in_existing_context(page, mode, mode_idx, official_map=None):
    """Play a mode using the existing page/context (preserves cookies)."""
    mode_name = mode["name"]
    mode_url = mode["url"]
    
    print(f"\n{'#'*60}")
    print(f"# Mode {mode_idx + 1}/{len(GAME_MODES)}: {mode_name}")
    print(f"# URL: {mode_url}")
    print(f"{'#'*60}\n")
    
    # Navigate to the mode and wait until the board is mounted + accepting
    # input. Skip gracefully instead of hanging when it never mounts.
    if not await enter_mode(page, mode):
        print(f"{mode_name}: skipped (board unavailable)")
        return
    
    # Wait for page to fully settle
    await asyncio.sleep(2)
    
    # Dismiss any residual popups
    await dismiss_welcome(page)
    await dismiss_popups(page)
    await asyncio.sleep(1)
    
    # Show transition screen
    await show_transition_screen(page, mode_name)
    
    # Play the mode (guided by official answers when available for this mode)
    official = (official_map or {}).get(mode_name)
    await play_single_mode(page, mode_name, official=official)


async def main():
    global winsList
    global numLosses
    
    script_dir = Path(__file__).parent
    video_dir = script_dir / "videos"
    video_dir.mkdir(exist_ok=True)
    
    mode_videos = []
    
    # Official daily answers (Wordle-style guarantee). Fetched once, synchronously,
    # before the browser loop. On failure this returns (None, {}) and every mode
    # falls back to the pure blind solver — the run continues either way.
    # Yesterday / tomorrow answers for the description recap + teaser.
    ytd_info = {}
    try:
        official_date, official_map = await asyncio.to_thread(fetch_official_quordle)
        if official_date:
            from datetime import timedelta as _td
            try:
                _od = datetime.strptime(official_date, "%Y-%m-%d")
            except Exception:
                _od = _target_quordle_date()
            _yd = _od - _td(days=1)
            _tdt = _od + _td(days=1)
            try:
                y_map = quordle_answers_local.get_quordle_for_date(_yd)
                ytd_info["yesterday"] = {"date": _yd.strftime("%Y-%m-%d"),
                                         "classic": y_map.get("Classic", []) or []}
            except Exception as _ye:
                print(f"[ytd] yesterday lookup failed: {_ye}")
            try:
                t_map = quordle_answers_local.get_quordle_for_date(_tdt)
                ttd = t_map.get("Classic", []) or []
                if ttd:
                    ytd_info["tomorrow"] = {"date": _tdt.strftime("%Y-%m-%d"),
                                            "classic": ttd}
            except Exception as _te:
                print(f"[ytd] tomorrow lookup failed: {_te}")
    except Exception as e:
        print(f"[official] unavailable, pure solver: {e}")
        official_date, official_map = None, {}
    
    async with async_playwright() as p:
        print(f"Starting browser (headless={HEADLESS})...")
        browser = await p.chromium.launch(headless=HEADLESS)
        
        # Create ONE persistent context for all modes.
        # BROWSER_TZ controls which calendar day the live MW Quordle board
        # shows. Default Asia/Tokyo (UTC+9): run in the evening IST and the
        # board is already on the NEXT day's puzzle. Local test can use
        # Pacific/Kiritimati (UTC+14) to prove next-day generation.
        _browser_tz = os.environ.get("BROWSER_TZ", "Asia/Tokyo")
        print(f"[tz] Quordle browser timezone: {_browser_tz}")
        context = await browser.new_context(
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
            timezone_id=_browser_tz,
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await context.route("**/*", block_ads)
        # Time-travel trick (like extension): fake JS Date to NEXT day so
        # date-seeded boards serve tomorrow early. TZ already does most of
        # it; FAKE_DATE_ISO forces it explicitly for local Kiribati tests.
        try:
            _fake_iso = os.environ.get("FAKE_DATE_ISO", "").strip()
            if _fake_iso:
                await context.add_init_script(script=QP.get_fake_date_init_script(_fake_iso))
                print(f"[fakedate] JS Date frozen to {_fake_iso}")
            else:
                # Default: shift to target quordle date 00:05 local so boards roll
                try:
                    _tgt_iso = QP._target_iso_fallback() if hasattr(QP, "_target_iso_fallback") else None
                except Exception:
                    _tgt_iso = None
                if _tgt_iso:
                    await context.add_init_script(script=QP.get_fake_date_init_script(_tgt_iso))
        except Exception as _fe:
            print(f"[fakedate] skipped: {_fe}")
        page = await context.new_page()
        
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Play each mode in order. Track wall-clock start of each mode so we
        # can build REAL YouTube chapter timestamps from actual elapsed time.
        mode_start_times = []
        _t0 = time.time()
        for mode_idx, mode in enumerate(GAME_MODES):
            mode_start_times.append(time.time() - _t0)
            await play_mode_in_existing_context(page, mode, mode_idx, official_map)
        _total_elapsed = time.time() - _t0
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

    # verify gate: 4 boards x 6 modes = 24 wins, zero losses
    _expected = 4 * len(GAME_MODES)
    qw_solved = len(winsList) >= _expected and numLosses == 0
    print(f"[verify] boards won {len(winsList)}/{_expected} losses={numLosses} solved={qw_solved}")
    
    # Rename/Process the single video file
    final_video_path = mode_videos[0] if mode_videos else None

    # --- Wordle-parity assembly: recap(5s)+hints(10s)+gameplay+3x analysis(8s)+teaser(5s)
    # Target date for labels (browser day, not host clock)
    try:
        _tgt = _target_quordle_date()
    except Exception:
        _tgt = datetime.now()
    today = _tgt.strftime("%B %d, %Y")
    _date_short = _tgt.strftime("%b %d")
    _day_num = _tgt.timetuple().tm_yday
    _date_key = _tgt.strftime("%Y-%m-%d")
    classic_words = (official_map or {}).get("Classic") or []
    # Fetch rich analysis once for slides + description
    _analysis = {}
    try:
        if YOUTUBE_AVAILABLE:
            from youtube_upload import fetch_word_analysis as _fwa
            _all = []
            for _ws in (official_map or {}).values():
                _all.extend(_ws or [])
            _analysis = _fwa(_all) or {}
    except Exception as _e:
        print(f"[analysis] fetch skipped: {_e}")

    tmp_imgs = []
    def _mk(path, fn, *a):
        try:
            if fn(path, *a):
                tmp_imgs.append(path)
                return path
        except Exception as e:
            print(f"[segment] {fn.__name__} failed: {e}")
        return None

    # Build segment images (Pillow-only, best-effort)
    recap_p = _mk(str(script_dir / f"recap_{_date_key}.png"), QP.generate_quordle_recap_image, ytd_info)
    hints_p = _mk(str(script_dir / f"hints_{_date_key}.png"), QP.generate_quordle_hints_image, today, classic_words)
    letter_freq = QP.get_letter_frequency_info(classic_words)
    def_p = _mk(str(script_dir / f"analysis_def_{_date_key}.png"), QP.generate_quordle_definition_slide, today, classic_words, _analysis)
    freq_p = _mk(str(script_dir / f"analysis_freq_{_date_key}.png"), QP.generate_quordle_frequency_slide, today, classic_words, letter_freq)
    facts_p = _mk(str(script_dir / f"analysis_facts_{_date_key}.png"), QP.generate_quordle_facts_slide, today, classic_words)
    teaser_p = _mk(str(script_dir / f"teaser_{_date_key}.png"), QP.generate_quordle_teaser_image, ytd_info)

    chapters = []
    if final_video_path and MOVIEPY_AVAILABLE:
        try:
            gameplay = VideoFileClip(str(final_video_path))
            # Split gameplay proportionally into 6 mode chapters using wall-clock ratios
            _weights = []
            for i in range(len(GAME_MODES)):
                s = mode_start_times[i] if i < len(mode_start_times) else 0
                e = mode_start_times[i+1] if i+1 < len(mode_start_times) else _total_elapsed
                _weights.append(max(1.0, e - s))
            _tot_w = sum(_weights) or 1.0
            _gd = float(gameplay.duration or 0)
            parts, cursor = [], 0.0
            def _img_clip(p, dur):
                return ImageClip(p).set_duration(dur).set_fps(24).resize(width=1920, height=1080)
            if recap_p:
                chapters.append((cursor, "Yesterday's Quordle recap"))
                c = _img_clip(recap_p, 5); parts.append(c); cursor += 5
            if hints_p:
                chapters.append((cursor, "Hints for all 4 words"))
                c = _img_clip(hints_p, 10); parts.append(c); cursor += 10
            # gameplay split
            _off = 0.0
            for i, m in enumerate(GAME_MODES):
                frac = _weights[i] / _tot_w
                dur = _gd * frac
                if i == 0:
                    chapters.append((cursor, f"{m['name']} Mode Solve"))
                # sub-chapters inside gameplay: offset from cursor
                if i > 0:
                    chapters.append((cursor + _off, f"{m['name']} Mode Solve"))
                _off += dur
            parts.append(gameplay)
            cursor += _gd
            if def_p:
                chapters.append((cursor, "Word analysis & definitions"))
                c = _img_clip(def_p, 8); parts.append(c); cursor += 8
            if freq_p:
                chapters.append((cursor, "Letter frequency analysis"))
                c = _img_clip(freq_p, 8); parts.append(c); cursor += 8
            if facts_p:
                chapters.append((cursor, "Word facts & solve path"))
                c = _img_clip(facts_p, 8); parts.append(c); cursor += 8
            if teaser_p:
                chapters.append((cursor, "Tomorrow's teaser"))
                c = _img_clip(teaser_p, 5); parts.append(c); cursor += 5
            final_clip = concatenate_videoclips(parts, method="compose")
            # ONE consistent music track over FULL video (Wordle parity)
            try:
                songs = [f for f in os.listdir(script_dir) if f.endswith('.mp3') and f.startswith('song')]
                if songs:
                    song_clip = AudioFileClip(str(script_dir / random.choice(songs)))
                    if song_clip.duration < final_clip.duration:
                        full_audio = afx.audio_loop(song_clip, duration=final_clip.duration)
                    else:
                        full_audio = song_clip.subclip(0, final_clip.duration)
                    final_clip = final_clip.set_audio(full_audio)
            except Exception as _ae:
                print(f"[audio] uniform mix failed: {_ae}")
            out_path = str(video_dir / f"quordle_final_{_date_key}.mp4")
            final_clip.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24)
            final_video_path = out_path
            print(f"[assembly] Wordle-parity video: {out_path} chapters={chapters}")
        except Exception as _e:
            print(f"[assembly] moviepy failed, using raw + music: {_e}")
            final_video_path = QP.apply_uniform_music_ffmpeg(str(final_video_path), script_dir)
    elif final_video_path:
        # ffmpeg fallback: uniform music only
        final_video_path = QP.apply_uniform_music_ffmpeg(str(final_video_path), script_dir)

    for _p in tmp_imgs:
        pass  # keep for debugging; CI cleans workspace anyway

    # Upload to YouTube
    if YOUTUBE_AVAILABLE and final_video_path:
        title = QP.build_optimized_title(_date_short, _day_num)
        if not chapters:
            # fallback: per-mode wall-clock chapters
            _mode_names = [m["name"] for m in GAME_MODES]
            for i, mn in enumerate(_mode_names):
                sec = int(round(mode_start_times[i])) if i < len(mode_start_times) else 0
                chapters.append((sec, f"{mn} Mode Solve"))
            chapters.append((int(round(_total_elapsed)), "All Modes Complete!"))
        print(f"[chapters] {chapters}")
        # Custom thumbnail (best-effort; upload proceeds even if it fails).
        thumb_path = None
        try:
            tp = str(script_dir / f"thumbnail_quordle_{_tgt.strftime('%Y-%m-%d')}.png")
            if generate_quordle_thumbnail(tp, today, official_map):
                thumb_path = tp
        except Exception as _te:
            print(f"[thumbnail] generation skipped: {_te}")
        # Pass official answers so the uploader builds an SEO description with
        # per-mode answers + AI word meanings (gemini proxy) + set thumbnail.
        video_id = upload_to_youtube(
            str(final_video_path), title=title,
            official_map=official_map, chapters=chapters,
            thumbnail_path=thumb_path, ytd_info=ytd_info
        )
        
        if video_id:
            # Trigger repository update
            print(f"Updating Video Repository Listing for ID: {video_id}...")
            try:
                # The script is now in the SAME folder as solver.py
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_video_listing.py")
                if os.path.exists(script_path):
                     # Capture output to ensure we see it in CI logs
                     result = subprocess.run(
                        ["python", script_path, video_id], 
                        check=False, 
                        capture_output=True, 
                        text=True
                     )
                     print("--- Update Script Output ---")
                     print(result.stdout)
                     print("--- Update Script Errors ---")
                     print(result.stderr)
                     print("----------------------------")
                     
                     if result.returncode == 0:
                        print("Repository listing updated successfully!")
                     else:
                        print(f"Update script failed with code {result.returncode}")
                else:
                    print(f"Warning: Update script not found at {script_path}")
            except Exception as e:
                print(f"Failed to execute update script: {e}")
                
    else:
        print("Skipping YouTube upload.")
    
    import json as _json
    try:
        _rk = _tgt.strftime("%Y-%m-%d")
    except Exception:
        _rk = datetime.now().strftime("%Y-%m-%d")
    (video_dir / f"result_{_rk}.json").write_text(_json.dumps(
        {"game": "quordle", "date": _rk, "solved": bool(qw_solved),
         "wins": len(winsList), "expected": _expected, "losses": numLosses,
         "video": str(final_video_path)}, indent=1))
    print("Done!" if qw_solved else "NOT SOLVED — see result json")
    import sys as _sys
    _sys.exit(0 if qw_solved else 1)


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
