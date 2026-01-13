/**
 * UI Controller for Quordle Solver X
 */

let solver;
let currentGuess = "";
const boardsData = [
    { guesses: [], results: [] },
    { guesses: [], results: [] },
    { guesses: [], results: [] },
    { guesses: [], results: [] }
];

document.addEventListener('DOMContentLoaded', () => {
    // Initialize solver with word lists from words.js
    solver = new QuordleSolver(MASTER_WORD_LIST, REST_WORD_LIST);

    const initialSuggestion = solver.findBestWord();
    updateSuggestion(initialSuggestion);

    const submitBtn = document.getElementById('submit-btn');
    const guessInput = document.getElementById('guess-input');

    submitBtn.addEventListener('click', handleGuess);
    guessInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleGuess();
    });
});

function updateSuggestion(word) {
    const suggestionEl = document.getElementById('next-suggestion');
    suggestionEl.textContent = word;
}

function handleGuess() {
    const input = document.getElementById('guess-input');
    const word = input.value.toUpperCase();

    if (word.length !== 5) {
        alert("Please enter a 5-letter word.");
        return;
    }

    if (!MASTER_WORD_LIST.includes(word) && !REST_WORD_LIST.includes(word)) {
        if (!confirm("Word not in list. Continue anyway?")) return;
    }

    currentGuess = word;
    addGuessToBoards(word);

    // Change Submit button to "GET NEXT SUGGESTION"
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.textContent = "GET BEST WORD";
    submitBtn.removeEventListener('click', handleGuess);
    submitBtn.addEventListener('click', calculateNext);

    // Clear input
    input.value = "";
    input.blur();
}

function addGuessToBoards(word) {
    for (let i = 0; i < 4; i++) {
        const boardContent = document.getElementById(`board-content-${i}`);
        const row = document.createElement('div');
        row.className = 'guess-row current-guess-row';
        row.dataset.rowIdx = boardsData[i].guesses.length;

        // Initialize default results as 'I' (Incorrect/Gray)
        const results = ['I', 'I', 'I', 'I', 'I'];
        boardsData[i].guesses.push(word);
        boardsData[i].results.push(results);

        for (let j = 0; j < 5; j++) {
            const tile = document.createElement('div');
            tile.className = 'tile gray';
            tile.textContent = word[j];
            tile.dataset.tileIdx = j;
            tile.dataset.boardIdx = i;

            tile.addEventListener('click', () => toggleColor(tile, i, boardsData[i].guesses.length - 1, j));
            row.appendChild(tile);
        }
        boardContent.appendChild(row);
    }
}

function toggleColor(tile, boardIdx, rowIdx, tileIdx) {
    const colors = ['gray', 'yellow', 'green'];
    const codes = ['I', 'M', 'C'];

    let currentIndex = 0;
    if (tile.classList.contains('yellow')) currentIndex = 1;
    else if (tile.classList.contains('green')) currentIndex = 2;

    let nextIndex = (currentIndex + 1) % 3;

    // Update UI
    tile.classList.remove(...colors);
    tile.classList.add(colors[nextIndex]);

    // Update data
    boardsData[boardIdx].results[rowIdx][tileIdx] = codes[nextIndex];
}

function calculateNext() {
    const currentGuessIdx = boardsData[0].guesses.length - 1;
    const currentResults = [
        boardsData[0].results[currentGuessIdx],
        boardsData[1].results[currentGuessIdx],
        boardsData[2].results[currentGuessIdx],
        boardsData[3].results[currentGuessIdx]
    ];

    solver.submitGuess(currentGuess, currentResults);

    const nextBest = solver.findBestWord();
    updateSuggestion(nextBest);

    // Reset Submit Button
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.textContent = "SUBMIT";
    submitBtn.removeEventListener('click', calculateNext);
    submitBtn.addEventListener('click', handleGuess);

    // Mark rows as non-interactive
    document.querySelectorAll('.current-guess-row').forEach(row => {
        row.classList.remove('current-guess-row');
        row.querySelectorAll('.tile').forEach(tile => {
            // Remove click listeners or make them static
            tile.style.cursor = 'default';
            // We can actually just leave them if user wants to correct, but solver already processed.
        });
    });
}
