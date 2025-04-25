import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import socket
import numpy as np

# Connect to Livesplit server
ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ls.connect(("localhost", 16834))

#Define getter to recieve Livesplit data
def lsGet(command):
    ls.send((command + "\r\n").encode())
    return ls.recv(1024).decode()[:-2]

chart_data = pd.DataFrame(
     np.random.randn(20, 3),
     columns=['a', 'b', 'c'])

st.line_chart(chart_data)