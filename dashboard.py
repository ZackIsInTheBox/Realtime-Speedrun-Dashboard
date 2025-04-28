import streamlit as st
import pandas as pd
import socket
import altair as alt
import plotly.graph_objects as go
import plotly.express as px
from _plotly_utils.exceptions import PlotlyError
import math
import saltysplits as ss
import json
import numpy as np
import time
import random

lsCommands = ["getdelta",
              "getlastsplittime",
              "getcurrenttime",
              "getfinaltime",
              "getpredictedtime",
              "getbestpossibletime",
              "getsplitindex",
              "getcurrentsplitname",
              "getprevioussplitname"]

# -----Define LiveSplit Server Functions----------------------------------------------------

# Connect to Livesplit server
try:
    ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ls.connect(("localhost", 16834))
except ConnectionRefusedError:
    st.warning("Could not establish connection to Livesplit Server")
    time.sleep(2)
    st.rerun()

def splitToSeconds(time):
    if time is None:
        return None
    if time[0] == '\u2212':  # Runner uses offset (uses unicode '-' not ASCII)
        return 0
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

def secondsToHMS(seconds):
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}"
    else:
        return f"{minutes}:{secs:02}"

def timedeltaToHMS(timedelta):
    seconds = int(timedelta.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

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

def getBPT():
    index = lsGet("getbestpossibletime")
    return splitToSeconds(index)

# ----Preamble----------------------------------------------------

def makeSplitDF():  # Create dataframe for live splits
    st.session_state.liveSplits = [{'Split': 0, 'Delta': 0}]  # Create empty split list
    st.session_state.liveSplits.append({'Split': getCurrentTime(),  # Create new current
                                    'Delta': st.session_state.liveSplits[-1]['Delta']})
makeSplitDF()

# Create SaltySplits object for splits file
splits = ss.read_lss(lss_path="dummySplits.lss")

# Store pb times
pbTimes = []
for i in range(len(splits.segments)):
    seg = json.loads(splits.segments[i].split_times[0].model_dump_json())
    pbTimes.append(splitToSeconds(seg['real_time']))

# Store best segments
goldTimes = []
for i in range(len(splits.segments)):
    seg = json.loads(splits.segments[i].best_segment_time.model_dump_json())
    goldTimes.append(splitToSeconds(seg['real_time']))

# Store split names
splitNames = []
for i in range(len(splits.segments)):
    splitNames.append(splits.segments[i].name)

# Stores the number of runs were all splits were completed
fullRuns = len(splits.to_df(cumulative=True, allow_partial=False).columns)

# Store 100 most recent runs
recentRuns = []
for i in range(len(splits.segments)):
    segs = []
    for j in range(max(-fullRuns, -100), -1):
        seg = json.loads(splits.segments[i].segment_history[j].model_dump_json())
        segs.append(splitToSeconds(seg['real_time']))
    segs = [x for x in segs if x is not None]  # Remove None values (skipped splits)
    # Remove outliers (1.5x upper percentile (no point removing lower percentile))
    if len(segs) > 0:
        q1 = np.percentile(segs, 25)
        q3 = np.percentile(segs, 75)
        iqr = q3 - q1
        upper_bound = q3 + 2 * iqr
        segs = [x for x in segs if x <= upper_bound]
    recentRuns.append(segs)


# ----Create Features-----------------------------------------------------

def PaceBar():
    def makeLine(df):
        line = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X('Split:Q', axis=alt.Axis(labels=False), title=None),
            y=alt.Y('Delta:Q', axis=alt.Axis(labels=False, title=None),
                    scale=alt.Scale(domain=[df['Delta'].min(),df['Delta'].max()]))).properties(
            width=600, height=300).interactive()
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

        del st.session_state.liveSplits[-1]  # Delete last current point
        currentSplit = len(st.session_state.liveSplits) - 1  # No. of splits = size of DF (minus current)

        if int(getIndex()) < currentSplit:  # UNDO
            del st.session_state.liveSplits[-1]  # Delete last split
            currentSplit -= 1

        if int(getIndex()) > currentSplit:  # SPLIT/SKIP
            if getLastSplitTime() != 0.0:  # SPLIT
                st.session_state.liveSplits.append({'Split': getLastSplitTime(), 'Delta': getDelta()})
            else:  # SKIP
                st.session_state.liveSplits.append({'Skip': 0,
                    'Delta': st.session_state.liveSplits[-1]['Delta']})  # SKIP - add dummy data
            currentSplit += 1

        # Add back current point
        st.session_state.liveSplits.append({'Split': getCurrentTime(),
                                       'Delta': st.session_state.liveSplits[-1]['Delta']})

        # Create the line chart
        df = pd.DataFrame(st.session_state.liveSplits)
        makeLine(df)

    else:  # If timer is inactive
        makeSplitDF()
        df = pd.DataFrame(st.session_state.liveSplits)  # Create DataFrame
        makeLine(df)

def SplitRings():
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
        x0 = 0.5 + 0.265 * math.cos(math.radians(angle))  # These values were trial and error
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
        return fig

    col1, col2, col3 = st.columns(3)
    with col3:  # Current split ring
        try:
            currentSplit = int(getIndex())
            splitProgression = ((getCurrentTime() -
                                 st.session_state.liveSplits[-2]['Split']) /
                                pbTimes[currentSplit])
            goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit] -
                                                          pbTimes[currentSplit-1]))
            st.plotly_chart(makeRing(splitProgression, 300, splitNames[currentSplit],
                                     goldProgression),
                            use_container_width=True)
        except (IndexError, KeyError, TypeError) as skipped:
            st.warning("Split skipped")
            pass

    with col2:  # Previous split ring
        if getIndex() - 1 >= 0:
            try:
                currentSplit = int(getIndex()) - 1
                splitProgression = ((st.session_state.liveSplits[-2]['Split'] -
                                     st.session_state.liveSplits[-3]['Split']) /
                                    pbTimes[currentSplit])
                goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit] -
                                                              pbTimes[currentSplit-1]))
                st.plotly_chart(makeRing(splitProgression, 150,
                                         splitNames[currentSplit],
                                         goldProgression),
                        use_container_width=True)
            except (IndexError, KeyError, TypeError) as skipped:
                st.warning("Split skipped")
                pass

    with col1:  # Second previous split ring
        if getIndex() - 2 >= 0:
            try:
                currentSplit = int(getIndex()) - 2
                splitProgression = ((st.session_state.liveSplits[-3]['Split'] -
                                     st.session_state.liveSplits[-4]['Split']) /
                                    pbTimes[currentSplit])
                goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit] -
                                                              pbTimes[currentSplit-1]))
                st.plotly_chart(makeRing(splitProgression, 150,
                                         splitNames[currentSplit],
                                         goldProgression),
                                use_container_width=True)
            except (IndexError, KeyError, TypeError) as skipped:
                st.warning("Split skipped")
                pass

def ConsistencyTracker():
    currentSplit = int(getIndex())

    splitName = splitNames[currentSplit]
    data = recentRuns[currentSplit]
    df = pd.DataFrame({'Split Time (s)': data, 'Split': splitName})

    minTime, maxTime = min(data) - 10, max(data) + 10

    boxPlot = px.box(df, x='Split', y='Split Time (s)')

    boxPlot.update_layout(
        yaxis_title='Split Time (s)',
        height=400,
        width=600,
        margin=dict(l=40, r=40, t=40, b=40),
    )

    boxPlot.update_yaxes(
        range=[minTime, maxTime],
        tickvals=list(range(int(minTime), int(maxTime), 3)),  # Create labels on y-axis
        ticktext=[secondsToHMS(s) for s in range(int(minTime), int(maxTime), 3)],  # Convert labels to MM:SS
    )

    return boxPlot

def PBPotential(simulations):
    # Calculate PB potential - run X simulations on current pace, using random splits from recentRuns

    global pbPotential
    currentSplit = int(getIndex())
    simulatedSuccesses = 0
    for simulation in range(simulations):
        currentSimulation = st.session_state.liveSplits[-2]['Split']  # Set simulation to current run time
        for split in range(currentSplit, len(splits.segments)):  # Iterate through all remaining splits
            currentSimulation += random.choice(recentRuns[split])   # Add random recent time
        if currentSimulation < pbTimes[-1]:
            simulatedSuccesses += 1
        pbPotential = simulatedSuccesses / simulations * 100

    r = int(255 * (1 - (pbPotential / 100)))
    g = int(255 * (pbPotential / 100))
    b = 0
    colour = '#{0:02X}{1:02X}{2:02X}'.format(r, g, b)

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pbPotential,
        number={'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100],
                     'showticklabels': False},
            'bar': {'color': colour},
            }
    ))
    gauge.update_layout(height=400)

    return gauge

def RunSummary():
    attempts = splits.attempt_count
    # Find all finished runs by filtering runs where the last split is not empty
    finishedRuns = splits.to_df(cumulative=True, allow_partial=True).iloc[-1].dropna()
    # Compare each successive finished run to create a list of PBs
    pbs = []
    currentBest = pd.Timedelta(days=9999)
    for run in finishedRuns:
        if run < currentBest:
            pbs.append(run)
            currentBest = run

    avg = pd.DataFrame(finishedRuns.tail(min(fullRuns, 10))).mean()
    avg = timedeltaToHMS(avg[0])

    game = splits.game_name
    category = splits.category_name

    if attempts > 0:
        resetRate = (1 - (len(finishedRuns) / attempts)) * 100
        pbRate = (len(pbs) / attempts) * 100
    else:
        resetRate = 0
        pbRate = 0

    st.markdown(f"### 🎮 {game} - {category}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Attempts", value=attempts)
    col2.metric(label="Reset Rate", value=f"{resetRate:.1f}%")
    col3.metric(label="PB Rate", value=f"{pbRate:.1f}%")
    col4.metric(label="Average (Prev. 10)", value=avg)

    with st.container():
        df = pd.DataFrame(pbs, columns=['PBTimes'])
        df['FormattedTime'] = df['PBTimes'].apply(lambda x: str(x).split(".")[0]
                                                      if pd.notna(x) else None)
        df["DateTime"] = pd.to_datetime(df["PBTimes"], unit="ns")
        df['PB'] = range(1, len(df) + 1)

        line = alt.Chart(df, title=alt.Title("PB History")).mark_line().encode(
            x=alt.X('PB:Q', title='PB'),
            y=alt.Y('DateTime:T', title='PB Time', axis=alt.Axis(format='%H:%M:%S')),
            tooltip=[alt.Tooltip('FormattedTime:N', title='Split Time')]
        )

        st.altair_chart(line, use_container_width=True)


# ----RunTime--------------------------------------------------------

st.set_page_config(layout="wide")

@st.fragment(run_every="1s")
def RunTime(min_attempts=10):
    try:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader('📈 Pace Bar')
                if getIndex() == -1:   # Check if timer is running
                    st.warning("Waiting for split data")
                else:
                    PaceBar()

            with st.container(border=True):
                st.subheader('⌛ Split Progression')
                if getIndex() == -1:   # Check if timer is running
                    st.warning("Waiting for split data")
                else:
                    SplitRings()

        if st.session_state.last_split != getIndex():  # Check if split has changed
            if fullRuns > min_attempts:  # Check if enough data is available
                st.session_state.consistencyTracker = ConsistencyTracker()
            try:
                if fullRuns >= 1:  # Make sure there is data to analyse
                    st.session_state.pbPotential = PBPotential(simulations=100)
            except (IndexError, KeyError, TypeError) as skipped:
                pass

        with col2:
            with st.container(border=True):
                st.subheader('🎯 Consistency Tracker')
                if fullRuns < min_attempts:
                    st.warning("Not enough split history to analyse variance")
                elif getIndex() == -1:   # Check if timer is running
                    st.warning("Waiting for split data")
                else:
                    st.plotly_chart(st.session_state.consistencyTracker, use_container_width=True)

            with st.container(border=True):
                st.subheader('🚨 PB Potential')
                if fullRuns < 1:
                    st.warning("Not enough split history to analyse variance")
                elif getIndex() == -1:   # Check if timer is running
                    st.warning("Waiting for split data")
                else:
                    try:
                        st.plotly_chart(st.session_state.pbPotential, use_container_width=True)
                    except PlotlyError:
                        st.warning("Not enough split history to analyse variance")

                with st.expander("How is this calculated?", expanded=False):
                    st.write("100 potential runs are simulated using random segments from your"
                             " recent runs. Your PB Potential is the number of randomised simulated"
                             " runs that beat your PB.")

            with st.expander("📝 Run Summary", expanded=True):
                RunSummary()

        st.session_state.last_split = getIndex()

    except ConnectionAbortedError:
        st.warning("Could not establish connection to Livesplit Server")

min_attempts = 10
if fullRuns > min_attempts:  # Check if enough data is available
    st.session_state.consistencyTracker = ConsistencyTracker()
try:
    st.session_state.pbPotential = PBPotential(simulations=100)
except IndexError:
    st.session_state.pbPotential = 0
st.session_state.last_split = getIndex()
RunTime()