import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import socket
import numpy as np
import altair as alt
import csv
import plotly.graph_objects as go
import math

lsCommands = ["getdelta",
              "getlastsplittime",
              "getcurrenttime",
              "getfinaltime",
              "getpredictedtime",
              "getbestpossibletime",
              "getsplitindex",
              "getcurrentsplitname",
              "getprevioussplitname"]

#  -----Define Functions----------------------------------------------------

# Connect to Livesplit server
ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ls.connect(("localhost", 16834))


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

def secondsToDelta(seconds):
    isNegative = seconds < 0
    seconds = abs(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours >=1:
        timeStr = f"{hours:02}:{minutes:02}:{seconds:05.2f}"
    else:
        timeStr = f"{minutes:02}:{seconds:05.2f}"
    return f"-{timeStr}" if isNegative else f"+{timeStr}"

def lsGet(command):
    ls.send((command + "\r\n").encode())
    return ls.recv(1024).decode()[:-2]


def getCurrentTime():
    currentTime = lsGet("getcurrenttime")
    return splitToSeconds(currentTime)


def getLastSplitTime():
    splitTime = lsGet("getlastsplittime")
    return splitToSeconds(splitTime)


def getDelta():
    delta = lsGet("getdelta")
    deltaTime = splitToSeconds(delta[1:])
    if delta[0] == '−':
        return -deltaTime
    else:
        return deltaTime


def getIndex():
    index = lsGet("getsplitindex")
    return splitToSeconds(index)


#  ----Pace Bar-----------------------------------------------------

def makeLine(df):
    line = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('Split:Q', axis=alt.Axis(labels=False), title=None),
        y=alt.Y('Delta:Q', axis=alt.Axis(labels=False, title=None),
                scale=alt.Scale(domain=[df['Delta'].min(),df['Delta'].max()]))).properties(
        width=600, height=300, title='Pace Bar').interactive()
    zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray',
                                                              strokeDash=[4, 4]).encode(y='y:Q')
    # Background bands (as rectangles)
    background = alt.Chart(pd.DataFrame({
        'y': [-10000, 0],  # Y min/max of the green band
        'y2': [0, 10000],  # Y min/max of the red band
        'Color': ['green', 'red']
    })).mark_rect(opacity=0.1).encode(
        y='y:Q',
        y2='y2:Q',
        color=alt.Color('Color:N', scale=None)  # Use fixed colors
    )
    st.altair_chart(line + zero_line + background, use_container_width=True,)

if int(getIndex()) != -1:  # If timer is active
    if 'splits' not in st.session_state:  # Initialise split data
        st.session_state.splits = [{'Split': 0, 'Delta': 0}]  # Create empty split list
        st.session_state.splits.append({'Split': getCurrentTime(),  # Create new current
                                        'Delta': st.session_state.splits[-1]['Delta']})

    del st.session_state.splits[-1]  # Delete last current point
    currentSplit = len(st.session_state.splits) - 1

    if int(getIndex()) < currentSplit:  # UNDO
        del st.session_state.splits[-1]
        currentSplit -= 1

    if int(getIndex()) > currentSplit:  # SPLIT/SKIP
        if getLastSplitTime() != 0.0:  # SPLIT
            st.session_state.splits.append({'Split': getLastSplitTime(), 'Delta': getDelta()})
        else:
            st.session_state.splits.append({'Skip': 0,
                'Delta': st.session_state.splits[-1]['Delta']})  # SKIP - add dummy data
        currentSplit += 1

    # Add current time
    st.session_state.splits.append({'Split': getCurrentTime(),  # Create new current
                                   'Delta': st.session_state.splits[-1]['Delta']})

    # Create the line chart
    df = pd.DataFrame(st.session_state.splits)
    makeLine(df)

else:  # If timer is inactive
    st.session_state.splits = [{'Split': 0, 'Delta': 0}]
    st.session_state.splits.append({'Split': getCurrentTime(),  # Create new current
                                    'Delta': st.session_state.splits[-1]['Delta']})
    # Create DataFrame
    df = pd.DataFrame(st.session_state.splits)
    makeLine(df)


#  ----Split Indicators-----------------------------------------------------

# Get split data
splits = []
with open('dummySplits.csv', newline='') as csvfile:
    splitsReader = csv.reader(csvfile, delimiter=' ', quotechar='|')
    splitsReader.__next__()
    for row in splitsReader:
        splits.append(row[0].split(','))
prevSplit = 0
for split in splits:
    split[1] = splitToSeconds(split[1])  # Split Time
    split[2] = splitToSeconds(split[2])  # Gold Time
    split.append(split[1]-prevSplit)  # Segment Time
    prevSplit = split[1]
    # Get relative progress through split as decimal
    split.append((getCurrentTime() - st.session_state.splits[-2]['Split']) / split[3])

# Let it overfill, and turn red if so

# Create ring
def makeRing(splitProgression, size, label, gold):
    if splitProgression > 1:
        behind = True
        splitProgression -= 1
    else:
        behind = False

    # Make ring
    fig = go.Figure(go.Pie(
        values=[splitProgression, 1 - splitProgression],
        hole=0.7,
        marker_colors=['red' if behind else 'green', 'green' if behind else 'white'],
        textinfo='none',
        sort=False))

    # Add gold indicator
    angle = -360 * gold + 90
    x0 = 0.5 + 0.265 * math.cos(math.radians(angle))
    y0 = 0.5 + 0.265 * math.sin(math.radians(angle))
    x1 = 0.5 + 0.382 * math.cos(math.radians(angle))
    y1 = 0.5 + 0.382 * math.sin(math.radians(angle))
    fig.add_shape(
        type="line",
        x0=x0, y0=y0,
        x1=x1, y1=y1,
        line=dict(color="gold", width=3),
        xref="paper", yref="paper"
    )

    # Add split name in ring
    fig.update_layout(
        showlegend=False,
        margin=dict(t=0, b=0, l=0, r=0),
        annotations=[dict(text=label, x=0.5, y=0.5, font_size=24, showarrow=False)],
        width=size, height=size)
    return(fig)

col1, col2, col3 = st.columns(3)
with col3:
    split = splits[int(getIndex())]
    st.plotly_chart(makeRing(split[4], 300, split[0], split[2] / split[3]),
                    use_container_width=True)

with col2:
    if getIndex() - 1 >= 0:
        split = splits[int(getIndex()) - 1]
        splitProgression = (st.session_state.splits[-2]['Split'] -
                            st.session_state.splits[-3]['Split']
                            ) / split[3]
        st.plotly_chart(makeRing(splitProgression, 150, split[0], split[2] / split[3])
                        , use_container_width=True)

with col1:
    split = splits[int(getIndex())]
    if getIndex() - 2 >= 0:
        split = splits[int(getIndex()) - 2]
        splitProgression = (st.session_state.splits[-3]['Split'] -
                            st.session_state.splits[-4]['Split']
                            ) / split[3]
        st.plotly_chart(makeRing(splitProgression, 150, split[0], split[2] / split[3])
                        , use_container_width=True)


#  ----Repeat-----------------------------------------------------

time.sleep(1)
st.rerun()