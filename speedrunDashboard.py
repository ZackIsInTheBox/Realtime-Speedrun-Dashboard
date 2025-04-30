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
import argparse

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

def splitToSeconds(time):
    """
    Takes a time value as a string input (HH:MM:SS), and returns the number of seconds
    :param time: A string formatted HH:MM:SS
    :return: a float, the number of seconds
    """
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

def secondsToHMS(seconds):
    """
    Converts seconds to HH:MM:SS
    :param seconds: An integer or float number of seconds
    :return: a string, HH:MM:SS
    """
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}"
    else:
        return f"{minutes}:{secs:02}"

def timedeltaToHMS(timedelta):
    """
    Takes a pandas.Timedelta object and returns the HH:MM:SS
    :param timedelta: a pandas.Timedelta object
    :return: a string, HH:MM:SS
    """
    seconds = int(timedelta.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def lsGet(command):
    """
    Formats and forwards commands to the livesplit server
    :param command: a string, the command to be passed to the server
    :return: the decoded server reply
    """
    ls.send((command + "\r\n").encode())
    return ls.recv(1024).decode()[:-2]

def getCurrentTime():
    """
    Returns the current timer value of Livesplit
    :return: the current timer value, in seconds
    """
    currentTime = lsGet("getcurrenttime")
    return splitToSeconds(currentTime)

def getLastSplitTime():
    """
    Returns the last split time value of Livesplit
    :return: the last split time value of Livesplit, in seconds
    """
    splitTime = lsGet("getlastsplittime")
    return splitToSeconds(splitTime)

def getDelta():
    """
    Returns the current run delta value of Livesplit
    :return: the current run delta value of Livesplit, a positive or negative float
    """
    delta = lsGet("getdelta")
    deltaTime = splitToSeconds(delta[1:])
    if delta[0] == '−':
        return -deltaTime
    else:
        return deltaTime

def getIndex():
    """
    Returns the current split index value of Livesplit
    :return: the current split index value of Livesplit. -1 means the timer is not running
    """
    index = lsGet("getsplitindex")
    return splitToSeconds(index)

def makeSplitDF():
    """
    Creates a blank dataframe for storing current run split data in the Streamlit session storage.
    The first "split" point is 0, and the second is the current timer value
    """
    st.session_state.liveSplits = [{'Split': 0, 'Delta': 0}]  # Create empty split list
    st.session_state.liveSplits.append({'Split': getCurrentTime(),  # Create new current
                                        'Delta': st.session_state.liveSplits[-1]['Delta']})

# ----Create Features-----------------------------------------------------

def PaceBar():
    """
    Creates a Streamlit chart that displays the runners current pace as a line graph. Every time
    this function is called, it will check if a new split / skip / undo has happened and append
    and delete the corresponding split data. It then updates the current timer value and builds the
    pace bar.
    :return:
    """
    def makeLine(df):
        """
        Constructs a Streamlit chart displaying the runner's current pace, based off the session
        state live split data.
        :param df: a dataframe of the current session state live split data. 'Split' values will
                   be displayed on the graph, with 'Delta' value
        """
        # Define line graph
        line = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X('Split:Q', axis=alt.Axis(labels=False), title=None),
            y=alt.Y('Delta:Q', axis=alt.Axis(labels=False, title=None),
                    scale=alt.Scale(domain=[df['Delta'].min(),df['Delta'].max()]))).properties(
            width=600, height=300).interactive()

        # Define line at y=0 (PB line)
        pbLine = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray',
                                                                  strokeDash=[4, 4]).encode(y='y:Q')

        # Create coloured rectangles that go above and below the PB line
        background = alt.Chart(pd.DataFrame({
            'y': [-10000, 0],  # Y min/max of the green band
            'y2': [0, 10000],  # Y min/max of the red band
            'Color': ['green', 'red']
        })).mark_rect(opacity=0.1).encode(
            y='y:Q',
            y2='y2:Q',
            color=alt.Color('Color:N', scale=None)  # Use fixed colors
        )
        # Construct graph
        st.altair_chart(line + pbLine + background, use_container_width=True)

    if int(getIndex()) != -1:  # If timer is active

        del st.session_state.liveSplits[-1]  # Delete last current point
        currentSplit = len(st.session_state.liveSplits) - 1  # No. of splits = size of DF (minus 0 split)

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
    """
    Constructs a Plotly chart, displayed with Streamlit, visualising the current and previous two
    segments as rings. 12 o'clock on the ring represents the runner's PB time, and the ring fills up
    green as the split progresses. If the runner loses time, the ring will overfill red. A gold marker
    represents the runner's gold time for a segment.
    """
    def makeRing(splitProgression, size, label, gold):
        """
        Constructs a "split ring" defined above.
        :param splitProgression: The float ratio of the timer through the segment (0-1)
        :param size: the integer size of the split ring
        :param label: the string name of the current split
        :param gold: the float gold ratio of the segment gold time through the PB, (0-1)
        :return: the split ring as a Plotly figure
        """
        # Determine if the runner is behind or ahead in the current segment
        if splitProgression > 1:
            behind = True
            splitProgression -= 1
        else:
            behind = False

        # Make split ring figure
        splitRing = go.Figure(go.Pie(
            values=[splitProgression, 1 - splitProgression],
            hole=0.7,
            marker_colors=['red' if behind else 'green', 'green' if behind else 'white'],
            textinfo='none',
            sort=False))

        # Determine angle of gold indicator on circle, and draw a line in its place.
        angle = -360 * gold + 90
        x0 = 0.5 + 0.265 * math.cos(math.radians(angle))  # These values were trial and error
        y0 = 0.5 + 0.265 * math.sin(math.radians(angle))
        x1 = 0.5 + 0.382 * math.cos(math.radians(angle))
        y1 = 0.5 + 0.382 * math.sin(math.radians(angle))
        splitRing.add_shape(
            type="line",
            x0=x0, y0=y0,
            x1=x1, y1=y1,
            line=dict(color="gold", width=3),
            xref="paper", yref="paper"
        )

        # Add split name in ring
        splitRing.update_layout(
            showlegend=False,
            margin=dict(t=0, b=0, l=0, r=0),
            annotations=[dict(text=label, x=0.5, y=0.5, font_size=24, showarrow=False)],
            width=size, height=size)

        return splitRing

    # Create 3 split rings of current split and previous two splits
    col1, col2, col3 = st.columns(3)
    with col3:  # Current split ring
        try:
            currentSplit = int(getIndex())
            splitProgression = ((getCurrentTime() -
                                 st.session_state.liveSplits[-2]['Split']) /
                                (pbTimes[currentSplit + 1] - pbTimes[currentSplit]))
            goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit + 1] -
                                                          pbTimes[currentSplit]))
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
                                    (pbTimes[currentSplit + 1] - pbTimes[currentSplit]))
                goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit + 1] -
                                                              pbTimes[currentSplit]))
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
                                    (pbTimes[currentSplit + 1] - pbTimes[currentSplit]))
                goldProgression = (goldTimes[currentSplit] / (pbTimes[currentSplit + 1] -
                                                              pbTimes[currentSplit]))
                st.plotly_chart(makeRing(splitProgression, 150,
                                         splitNames[currentSplit],
                                         goldProgression),
                                use_container_width=True)
            except (IndexError, KeyError, TypeError) as skipped:
                st.warning("Split skipped")
                pass

def ConsistencyTracker():
    """
    Create a boxplot of the performance variation of the most recent (up to) 100 runs in the current
    segment.
    :return: a Plotly chart of the consistency boxplot
    """
    currentSplit = int(getIndex())

    # Retrieve segment data and create dataframe
    splitName = splitNames[currentSplit]
    data = recentRuns[currentSplit]
    df = pd.DataFrame({'Split Time (s)': data, 'Split': splitName})

    minTime, maxTime = min(data) - 10, max(data) + 10  # Define boundaries of box plot

    boxPlot = px.box(df, x='Split', y='Split Time (s)')  # Define box plot
    boxPlot.update_layout(
        yaxis_title='Split Time (s)',
        height=400,
        width=600,
        margin=dict(l=40, r=40, t=40, b=40),
    )

    # Replace Y axis labels with HH:MM:SS format, instead of seconds
    boxPlot.update_yaxes(
        range=[minTime, maxTime],
        # Create labels on y-axis at interval 3 (smaller interval = more labels)
        tickvals=list(range(int(minTime), int(maxTime), 5)),
        # Convert labels to MM:SS
        ticktext=[secondsToHMS(s) for s in range(int(minTime), int(maxTime), 5)],
    )

    return boxPlot

def PBPotential(simulations):
    """
    Calculates PB potential and creates a coloured gauge indicator to display it. Run "simulation"
    simulations against the current pace, using random splits from recentRuns to create a potential
    run. Each run is compared to PB, and the PB potential is the percentage of simulations that beat
    PB.
    :param simulations: The int number of simulations to run.
    :return: A plotly chart displaying the PB potential and a coloured gauge to visualise it.
    """

    global pbPotential  # Makes it so that PB potential is visible outside the for loop scope
    currentSplit = int(getIndex())
    simulatedSuccesses = 0
    for simulation in range(simulations):
        # Set simulation to current run time
        currentSimulation = st.session_state.liveSplits[-2]['Split']
        # Iterate through all remaining splits
        for split in range(currentSplit, len(splits.segments)):
            currentSimulation += random.choice(recentRuns[split])   # Add random recent time
        if currentSimulation < pbTimes[-1]:  # Determine if simulation was a success
            simulatedSuccesses += 1
        pbPotential = simulatedSuccesses / simulations * 100

    # Define HEX colour of bar as a ratio of red:green against the PB potential
    r = int(255 * (1 - (pbPotential / 100)))
    g = int(255 * (pbPotential / 100))
    b = 0
    colour = '#{0:02X}{1:02X}{2:02X}'.format(r, g, b)

    # Define the Plotly figure  displaying the PB potential and gauge
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
    """
    Creates a run summary panel displaying metadata drawn from the Livesplit file. This includes
    run name, category, attempt count, reset rate, pb rate, average run. and a line graph of PB
    history.
    """

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

    # Calculate the average run time from the runner's (up to) 10 most recent runs
    avg = pd.DataFrame(finishedRuns.tail(min(fullRuns, 10))).mean()
    avg = timedeltaToHMS(avg.iloc[0])

    game = splits.game_name
    category = splits.category_name

    # Calculate reset rate and PB rate
    if attempts > 0:  # Avoid divide by zero error
        resetRate = (1 - (len(finishedRuns) / attempts)) * 100
        pbRate = (len(pbs) / attempts) * 100
    else:
        resetRate = 0
        pbRate = 0

    # Write in text/numerical data
    st.markdown(f"### 🎮 {game} - {category}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Attempts", value=attempts)
    col2.metric(label="Reset Rate", value=f"{resetRate:.1f}%")
    col3.metric(label="PB Rate", value=f"{pbRate:.1f}%")
    col4.metric(label="Average (Prev. 10)", value=avg)

    # Create line chart of PB history
    with st.container():
        df = pd.DataFrame(pbs, columns=['PBTimes'])
        # Create a dataframe column of HH:MM:SS formatted times for displaying on the Y axis
        df['FormattedTime'] = df['PBTimes'].apply(lambda x: str(x).split(".")[0]
                                                      if pd.notna(x) else None)
        # Create dataframe column of comparable Datetime values
        df["DateTime"] = pd.to_datetime(df["PBTimes"], unit="ns")
        # Number the PBs
        df['PB'] = range(1, len(df) + 1)

        # Define line chart
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
    """
    The run time environment for the dashboard, constructing all the elements and displaying them.
    :param min_attempts: The integer minimum number of attempts to run the performance variation modules (consistency
    tracker, PB potential)
    """
    try:
        if len(st.session_state.liveSplits) - 2 != getIndex():  # Check if split has changed
            splitChange = True
        else:
            splitChange = False

        col1, col2 = st.columns(2)
        # Pace bar, Split Progression
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

            with st.expander("📝 Run Summary", expanded=True):
                if splitChange: RunSummary()


        if fullRuns > min_attempts:  # Check if enough data is available
            try:
                if splitChange: st.session_state.consistencyTracker = ConsistencyTracker()
            except (IndexError, KeyError, TypeError) as skipped:
                pass
        try:
            if fullRuns >= 1:  # Make sure there is data to analyse
                if splitChange: st.session_state.pbPotential = PBPotential(simulations=100)
        except (IndexError, KeyError, TypeError) as skipped:
            pass

        # Consistency Tracker, PB Potential Gauge, collapsable Run Summary
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

    except ConnectionAbortedError:
        st.warning("Could not establish connection to Livesplit Server")

def main(args):
    global ls
    global pbTimes
    global goldTimes
    global splitNames
    global recentRuns
    global splits
    global recentRuns
    global fullRuns

    # Connect to Livesplit server
    try:
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.connect(("localhost", 16834))
    except ConnectionRefusedError:
        st.warning("Could not establish connection to Livesplit Server")
        time.sleep(2)
        st.rerun()

    # Create SaltySplits object for splits file
    splits = ss.read_lss(lss_path=args.splitFile)

    # Store pb times
    pbTimes = [0]
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
        for j in range(max(-fullRuns, -100), -1):  # If splits contain less than 100 runs, take max
            seg = json.loads(splits.segments[i].segment_history[j].model_dump_json())
            segs.append(splitToSeconds(seg['real_time']))

        segs = [x for x in segs if x is not None]  # Remove None values (skipped splits)

        # Remove outliers (1.5x upper percentile (no point removing lower percentile))
        if len(segs) > 0:
            q1 = np.percentile(segs, 25)
            q3 = np.percentile(segs, 75)
            iqr = q3 - q1
            upper_bound = q3 + 1.5 * iqr
            segs = [x for x in segs if x <= upper_bound]
        recentRuns.append(segs)

    makeSplitDF()

    min_attempts = 10
    if fullRuns > min_attempts:  # Check if enough data is available
        st.session_state.consistencyTracker = ConsistencyTracker()
    try:
        st.session_state.pbPotential = PBPotential(simulations=100)
    except IndexError:
        st.session_state.pbPotential = 0

    RunTime()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Speedrun Dashboard")
    parser.add_argument("splitFile", type=str, help="Path to your split file")
    args = parser.parse_args()
    main(args)
