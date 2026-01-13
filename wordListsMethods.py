# Aidan Kelly

import csv
import math

letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']

def getAllWords():
    with open("masterWordList.csv", "r") as file:
        csvreader = csv.reader(file)
        for row in csvreader:
            return row
    
def getRestWords():    
    with open("restOfWords.csv", "r") as file:
        csvreader = csv.reader(file)
        for row in csvreader:
            return row        

def getLetterLikelihoods(wordsList):
    # Create Likelihoods Variable
    spotLikelihoods = []
    overallLikelihoods = []
    for i in range(5):
        # 5 spots
        spotLikelihoods.append([])

        for j in range(26):
            # 26 letters in each spot
            spotLikelihoods[i].append(0)

    for i in range(26):
        # 26 letters overall
        overallLikelihoods.append(0)
    
    for i in range(len(wordsList)):
        for j in range(5):
            for k in range(26):
                if wordsList[i][j] == letters[k]:
                    # add 3 points to letter in specific spot
                    spotLikelihoods[j][k] += 3

                    # add 1 point to overall letter
                    overallLikelihoods[k] += 1

    """
    print("Spot")
    print(spotLikelihoods)
    print("Overall")
    print(overallLikelihoods)
    print()
    """

    for ltr in range(26):
        for spot in range(5):
            spotLikelihoods[spot][ltr] += overallLikelihoods[ltr]
    """
    print("New Spot")
    print(spotLikelihoods)
    print()
    print()
    print()
    """
    return spotLikelihoods



def wordContains(word, letter):
    for i in range(5):
        if word[i] == letter:
            return True
    return False


def totalLetterLikelihoods(llh):
    newList = []
    for i in range(26):
        newList.append(llh[0][i] + llh[1][i] + llh[2][i] + llh[3][i] + llh[4][i])
        #print(newList[i])
        newList[i] = math.ceil(newList[i] / 8)
    return newList


def getDupsIndexList(ltrIndex, wrd):
    sameLetterIndexList = []
    for i in range(5):
        if wrd[i] == wrd[ltrIndex]:
            sameLetterIndexList.append(i)
    return sameLetterIndexList

