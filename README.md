# optionspreaddashboard
Streamlit Dashboard for screening option vertical spread, using CBOE data and RDP

It has a bunch of functions that it calls, which generally cleans data. Then I plot them on the streamlit dashboard.

main.py: main function to run the streamlit dashboard and define the layouts
vectorised_load_data.py: functions to scrap CBOE data and combine into spreads
ifa_files (Directory): codes to connect to RDP IPA (instrument pricing analytics). IDK why I wrote it as IFA
eti_surfaces.py: Get surface object from RDP (raw data). The instrument list (RICs) is hardcoded in the function. (should find the corresponding RICs for each ticker in config)
plotting_helper.py: Plot the various graphs from the raw surface object
hist_atmvol.py: Function to get historical ATM 3-month put implied volatility of each ticker from RDP

Please add in new functionalities of the dashboard.
