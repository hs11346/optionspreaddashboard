from vectorised_load_data import *
import time

'''
Streamlit Dashboard for hosting CBOE 
'''
def get_config():
    config = pd.read_csv('config.csv')
    return config.Tickers.to_list(), config

@st.cache_data(ttl=3600) # reload cache every 3600 seconds
def load_data():
    freeze_support()
    put = PCS_screener(list_, max_strike_width=3, min_dte=0, max_dte=30, fees=0.1, min_dist=1, min_bid=0.2)
    freeze_support()
    call = CCS_screener(list_, max_strike_width=3, min_dte=0, max_dte=30, fees=0.1, min_dist=1, min_bid=0.2)
    return put, call

if __name__=="__main__":
    start_time = time.time()
    #1204.6977639198303 seconds (unvectorised)
    #118.43037843704224 seconds (vectorised)
    st.title('Option Spread Monitor')
    list_, config = get_config()
    px_df = px_screener(config, upper=70, lower=30)
    put, call = load_data()
    st.title('Welcome to the CBOE Option Vertical Spread Monitor v3.0')
    option = st.sidebar.selectbox(
        'Ticker',
        list_)
    max_width = st.sidebar.slider('Max Width', 0, 3, 3, 1)
    max_dte = st.sidebar.slider('Max DTE', 0, 30, 30, 1)
    min_dist = st.sidebar.slider('Min Distance', 1.1, 3.0, 1.1, 0.1)
    min_bid = st.sidebar.slider('Min bid', 0.2, 0.5, 0.2, 0.01)
    tab1, tab2, tab3 = st.tabs(["PCS", "CCS", 'Underlyings'])
    with tab1:
        st.markdown('Put Credit Spread:')
        filtered_put = put.loc[(put.underlying == option) & (put.width <= max_width) & (put.dte <= max_dte) & (put.ATM_dist >= min_dist) & (put.bid >= min_bid)]
        st.dataframe(filtered_put)
    with tab2:
        st.markdown('Call Credit Spread:')
        st.dataframe(call.loc[(call.underlying == option) & (call.width <= max_width) & (call.dte <= max_dte) & (call.ATM_dist >= min_dist) & (call.bid >= min_bid)])
    with tab3:
        px = px_screener(config)
        st.dataframe(px.sort_values(by='percentile',ascending=True))
    print("--- %s seconds ---" % (time.time() - start_time))