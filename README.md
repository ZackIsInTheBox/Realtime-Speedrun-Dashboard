# Before you run the dashboard
### Install requirements
Ensure you have Python 3.12 installed. Open the dashboard folder directory in a command-line, and run `pip install -r requirements.txt` to install the package dependencies.

### Format your split file
The SaltySplits Livesplit file parser currently causes a crash if you use a negative offset for your run --- it is recommended that you create a copy of your desired split file with no offset in the dashboard directory before each session which can be read by the program. Alternatively, remove your offset, save your splits, and re-add it without saving your splits before you run the dashboard. 

Make sure you have the Livesplit Server component within your Layout. This can be found in the "Control" tab when you add a component. It should be set to the port 16834 by default.

# Running the dashboard
To run the dashboard, run `streamlit run speedrunDashboard.py {SPLITS.lss}` from a command-line within the dashboard folder directory. This should open the dashboard in a browser window.

Don't forget to start the Livesplit server by right-clicking on your splits -> Control -> Start Server. If you change layout or re-open your splits this may have to be started again.

If the dashboard crashes or freezes, it can be restarted by refreshing the browser tab.
