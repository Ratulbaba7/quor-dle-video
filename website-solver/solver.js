/**
 * Core Quordle Solver Logic (Ported from Python)
 */

class QuordleSolver {
    constructor(masterWords, restWords) {
        this.letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'];
        this.allWords = [...masterWords];
        this.indivWords = [
            [...masterWords],
            [...masterWords],
            [...masterWords],
            [...masterWords]
        ];
        this.restOfWords = [...restWords];
        this.lettersUsed = new Array(26).fill(1);
        this.knowledgeList = [
            Array(5).fill(""),
            Array(5).fill(""),
            Array(5).fill(""),
            Array(5).fill("")
        ];
        this.resultsList = [
            Array(5).fill(""),
            Array(5).fill(""),
            Array(5).fill(""),
            Array(5).fill("")
        ];
        this.iteration = -1;
        this.avgLikelihoods = this.totalLetterLikelihoods(this.getLetterLikelihoods(this.allWords));
    }

    getLetterLikelihoods(wordsList) {
        let spotLikelihoods = Array.from({ length: 5 }, () => new Array(26).fill(0));
        let overallLikelihoods = new Array(26).fill(0);

        for (const word of wordsList) {
            for (let j = 0; j < 5; j++) {
                const charCode = word.charCodeAt(j) - 65;
                if (charCode >= 0 && charCode < 26) {
                    spotLikelihoods[j][charCode] += 3;
                    overallLikelihoods[charCode] += 1;
                }
            }
        }

        for (let ltr = 0; ltr < 26; ltr++) {
            for (let spot = 0; spot < 5; spot++) {
                spotLikelihoods[spot][ltr] += overallLikelihoods[ltr];
            }
        }
        return spotLikelihoods;
    }

    totalLetterLikelihoods(llh) {
        let newList = [];
        for (let i = 0; i < 26; i++) {
            let sum = 0;
            for (let j = 0; j < 5; j++) {
                sum += llh[j][i];
            }
            newList.push(Math.ceil(sum / 8));
        }
        return newList;
    }

    getDupsIndexList(ltrIndex, wrd) {
        let sameLetterIndexList = [];
        for (let i = 0; i < 5; i++) {
            if (wrd[i] === wrd[ltrIndex]) {
                sameLetterIndexList.push(i);
            }
        }
        return sameLetterIndexList;
    }

    getFillerWord(lettersList) {
        if (lettersList.length >= 4) {
            for (const word of this.restOfWords) {
                if (lettersList.slice(0, 4).every(l => word.includes(l))) return word;
            }
        }
        if (lettersList.length >= 3) {
            for (const word of this.restOfWords) {
                if (lettersList.slice(0, 3).every(l => word.includes(l))) return word;
            }
        }
        for (const word of this.restOfWords) {
            if (lettersList.slice(0, 2).every(l => word.includes(l))) return word;
        }
        return "XXXXX";
    }

    getMissingLetters(wordNum, ltr) {
        return this.indivWords[wordNum].map(w => w[ltr]);
    }

    getUnknownLetterPositions(wordList) {
        if (wordList.length === 0) return [];
        let unknownLtrPosList = [];
        for (let ltr = 0; ltr < 5; ltr++) {
            const firstChar = wordList[0][ltr];
            if (!wordList.every(w => w[ltr] === firstChar)) {
                unknownLtrPosList.push(ltr);
            }
        }
        return unknownLtrPosList;
    }

    minLenNot0() {
        let activeLengths = this.indivWords.filter(w => w.length > 0).map(w => w.length);
        return activeLengths.length > 0 ? Math.min(...activeLengths) : 0;
    }

    findBestWord() {
        // Step 1: Check for single possibilities
        for (let i = 0; i < 4; i++) {
            if (this.indivWords[i].length === 1 && this.resultsList[i].join('') !== "CCCCC") {
                return this.indivWords[i][0];
            }
        }

        let wordsLeft = 0;
        for (let i = 0; i < 4; i++) {
            if (this.resultsList[i].join('') !== "CCCCC") {
                wordsLeft++;
            }
        }

        let combinedWordsList = [];
        for (let i = 0; i < 4; i++) {
            if (this.indivWords[i].length > 0) {
                let unknownLetterPosns = this.getUnknownLetterPositions(this.indivWords[i]);
                if (unknownLetterPosns.length === 1 && this.indivWords[i].length > 2 && this.iteration !== 7) {
                    let missingLetters = this.getMissingLetters(i, unknownLetterPosns[0]);
                    combinedWordsList.push(this.getFillerWord(missingLetters));
                } else if (unknownLetterPosns.length === 2 && !this.resultsList[i].includes("M") && wordsLeft > 1) {
                    let missingLetters = [...new Set([...this.getMissingLetters(i, unknownLetterPosns[0]), ...this.getMissingLetters(i, unknownLetterPosns[1])])];
                    combinedWordsList.push(this.getFillerWord(missingLetters));
                } else {
                    combinedWordsList.push(...this.indivWords[i]);
                }
            }
        }

        if (combinedWordsList.length === 0) return "XXXXX";

        let likelihoods = this.getLetterLikelihoods(combinedWordsList);
        for (let i = 0; i < 5; i++) {
            for (let j = 0; j < 26; j++) {
                likelihoods[i][j] += (this.avgLikelihoods[j] * this.lettersUsed[j]);
            }
        }

        let maxVal = -1;
        let bestWord = combinedWordsList[0];

        for (const word of combinedWordsList) {
            let curWordValue = 0;
            for (let j = 0; j < 5; j++) {
                const charCode = word.charCodeAt(j) - 65;
                let dupeFactor = 1;
                const dups = this.getDupsIndexList(j, word).length;
                if (dups === 2) dupeFactor = 2 / 3;
                else if (dups === 3) dupeFactor = 0.5;
                curWordValue += (likelihoods[j][charCode] * dupeFactor);
            }

            if (this.iteration > 0) {
                let inListCounter = 0;
                let inMinLenList = false;
                let minLen = this.minLenNot0();

                for (let a = 0; a < 4; a++) {
                    if (this.indivWords[a].includes(word)) {
                        inListCounter++;
                        if (this.indivWords[a].length === minLen) inMinLenList = true;
                    }
                }
                if (inMinLenList && inListCounter === 1 && wordsLeft > 1) {
                    curWordValue = 0;
                }
            }

            if (curWordValue > maxVal) {
                maxVal = curWordValue;
                bestWord = word;
            }
        }

        return bestWord;
    }

    setLettersAsUsed(wrd) {
        for (let i = 0; i < 5; i++) {
            const charCode = wrd.charCodeAt(i) - 65;
            if (charCode >= 0 && charCode < 26) this.lettersUsed[charCode] = 0;
        }
    }

    submitGuess(guessWord, resultsPerBoard) {
        // resultsPerBoard is an array of 4 arrays, each with 5 letters: 'C' (Correct), 'M' (Misplaced), 'I' (Incorrect)
        this.iteration++;
        this.resultsList = resultsPerBoard;
        this.setLettersAsUsed(guessWord);
        this.removeWords(guessWord);
    }

    removeWords(lastWord) {
        for (let wordIdx = 0; wordIdx < 4; wordIdx++) {
            if (this.indivWords[wordIdx].length === 0) continue;

            const results = this.resultsList[wordIdx];
            if (results.join('') === "CCCCC") {
                this.indivWords[wordIdx] = [];
                continue;
            }

            // Remove the guessed word from possibilities
            const idxInList = this.indivWords[wordIdx].indexOf(lastWord);
            if (idxInList !== -1) this.indivWords[wordIdx].splice(idxInList, 1);
            if (this.indivWords[wordIdx].length === 0) continue;

            let filtered = [];
            for (const candidate of this.indivWords[wordIdx]) {
                let match = true;
                for (let i = 0; i < 5; i++) {
                    const res = results[i];
                    const char = lastWord[i];

                    if (res === "I") {
                        const dups = this.getDupsIndexList(i, lastWord);
                        if (dups.length > 1) {
                            const dupsResults = dups.map(idx => results[idx]);
                            if (dupsResults.includes("M") || dupsResults.includes("C")) {
                                if (candidate[i] === char) { match = false; break; }
                            } else {
                                if (candidate.includes(char)) { match = false; break; }
                            }
                        } else {
                            if (candidate.includes(char)) { match = false; break; }
                        }
                    } else if (res === "M") {
                        if (candidate[i] === char || !candidate.includes(char)) { match = false; break; }
                    } else if (res === "C") {
                        if (candidate[i] !== char) { match = false; break; }
                    }
                }
                if (match) filtered.push(candidate);
            }
            this.indivWords[wordIdx] = filtered;
        }
    }
}
