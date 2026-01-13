import csv
import os

# Create the target directory
os.makedirs('../website-solver', exist_ok=True)

# Read master words
with open('masterWordList.csv', 'r') as f:
    reader = csv.reader(f)
    master = next(reader)

# Read rest words
with open('restOfWords.csv', 'r') as f:
    reader = csv.reader(f)
    rest = next(reader)

# Write JS file
with open('../website-solver/words.js', 'w') as f:
    f.write('// Word lists for Quordle Solver\n')
    f.write('const MASTER_WORD_LIST = [\n')
    for i, w in enumerate(master):
        f.write(f'  "{w}"')
        if i < len(master) - 1:
            f.write(',')
        if (i + 1) % 10 == 0:
            f.write('\n')
    f.write('\n];\n\n')
    f.write('const REST_WORD_LIST = [\n')
    for i, w in enumerate(rest):
        f.write(f'  "{w}"')
        if i < len(rest) - 1:
            f.write(',')
        if (i + 1) % 10 == 0:
            f.write('\n')
    f.write('\n];\n')

print('words.js created successfully!')
