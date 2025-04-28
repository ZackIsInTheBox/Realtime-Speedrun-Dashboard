import csv
import requests
import xml.etree.ElementTree as ET

'''
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
'''

import saltysplits as ss
import json
import pandas as pd
from datetime import datetime, timedelta

# Loading (and validating) LSS file
splits = ss.read_lss(lss_path="dummySplits2.lss")

# Getting the first split of the first run (i.e. Time instance)
y = json.loads(splits.segments[0].split_times[0].model_dump_json())

dataframe = splits.to_df(cumulative=False, allow_partial=True)
# Getting best split for all segments (including those in partial runs)
best_segments = dataframe.min(axis=1)

print(len(splits.to_df(cumulative=True, allow_partial=False).columns
      ))
#print(best_segments)

finishedRuns = splits.to_df(cumulative=True, allow_partial=True).iloc[-1].dropna().tolist()
# Compare each successive finished run to create a list of PBs
