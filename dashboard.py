import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import socket
import numpy as np
import altair as alt

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

    # Create DataFrame
    df = pd.DataFrame(st.session_state.splits)
    df['FormattedDelta'] = df['Delta'].apply(secondsToDelta)
    # Create the line chart
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


else:
    st.session_state.splits = [{'Split': 0, 'Delta': 0}]
    st.session_state.splits.append({'Split': getCurrentTime(),  # Create new current
                                  'Delta': st.session_state.splits[-1]['Delta']})
    # Create DataFrame
    df = pd.DataFrame(st.session_state.splits)
    # Create the line chart
    chart = alt.Chart(df).mark_line(point=True).encode(
        x='Split:Q',
        y='Delta:Q'
    ).properties(
        width=600,
        height=300,
        title='Split Delta Over Time'
    ).interactive()
    st.altair_chart(chart, use_container_width=True)

#  ----Split Indicators-----------------------------------------------------

# Get split data


# Progress arc
progress_arc = alt.Chart(split_data).mark_arc(innerRadius=30, outerRadius=50).encode(
    theta=alt.Theta('Progress:Q', stack='zero'),  # angle = progress
    color=alt.value('steelblue')
)

# Background arc (full circle)
background_arc = alt.Chart(split_data).mark_arc(innerRadius=30, outerRadius=50, color='lightgray').encode(
    theta=alt.value(1)  # full circle
)

# Optional: Gold marker (use a tick or thin line if you want)
gold_marker = alt.Chart(split_data).mark_tick(thickness=2, color='gold', size=30).encode(
    theta=alt.Theta('GoldRatio:Q', scale=alt.Scale(domain=[0, 1])),
    radius=alt.value(55)
)

# Combine
chart = background_arc + progress_arc + gold_marker
st.altair_chart(chart, use_container_width=False)


#  ----Repeat-----------------------------------------------------

time.sleep(0.5)
st.rerun()
