import csv
def splitToSeconds(time):
    parts = time.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        return float(time)


splits = [[], [], []]

with open('dummySplits.csv', newline='') as csvfile:
    splitsReader = csv.reader(csvfile, delimiter=' ', quotechar='|')
    splitsReader.__next__()
    for row in splitsReader:
        splits.append(row[0].split(','))
splits = splits[3:]
prevSplit = 0
for split in splits:
    split[1] = splitToSeconds(split[1])
    split[2] = splitToSeconds(split[2])
    split.append(split[1]-prevSplit)
    prevSplit = split[1]

print(splits)