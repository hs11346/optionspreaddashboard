from vectorised_load_data import *
import time
import altair as alt

import datetime
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
@st.cache_data()
def yfinance_hist(option):
    return yf.download(option, interval='1d', period='1y')
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
        #st.dataframe(filtered_put)


        def dataframe_with_selections(df):
            df_with_selections = df.copy()
            df_with_selections.insert(0, "Select", False)

            # Get dataframe row-selections from user with st.data_editor
            edited_df = st.data_editor(
                df_with_selections,
                hide_index=True,
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=df.columns,
                key = option+'call'
            )

            # Filter the dataframe using the temporary column, then drop the column
            selected_rows = edited_df[edited_df.Select]
            return selected_rows.drop('Select', axis=1)
        selection = dataframe_with_selections(filtered_put)
        st.write("Your selection:")
        st.write(selection)
        # Graphing
        df = yfinance_hist(option)
        df.reset_index(inplace=True)
        c = alt.Chart(df).mark_line().encode(
            x='Date',
            y='Close'
        )
        c.encoding.y.scale = alt.Scale(domain=[df.Close.min()*0.95, df.Close.max()*1.05])
        line = alt.Chart(pd.DataFrame({'Close': selection.strike_short.to_list()})).mark_rule().encode(y='Close', color = alt.value("#FF0000"))
        st.header("\nPrice Chart (Red line indicating short strike)")
        st.altair_chart((c + line).interactive(), use_container_width=True)
    with tab2:
        st.markdown('Call Credit Spread:')
        filtered_call = call.loc[(call.underlying == option) & (call.width <= max_width) & (call.dte <= max_dte) & (call.ATM_dist >= min_dist) & (call.bid >= min_bid)]

        def dataframe_with_selections(df):
            df_with_selections = df.copy()
            df_with_selections.insert(0, "Select", False)

            # Get dataframe row-selections from user with st.data_editor
            edited_df = st.data_editor(
                df_with_selections,
                hide_index=True,
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=df.columns,
                key = option+"put"
            )

            # Filter the dataframe using the temporary column, then drop the column
            selected_rows = edited_df[edited_df.Select]
            return selected_rows.drop('Select', axis=1)
        selection = dataframe_with_selections(filtered_call)
        st.write("Your selection:")
        st.write(selection)
        # Graphing
        df = yfinance_hist(option)
        df.reset_index(inplace=True)
        c = alt.Chart(df).mark_line().encode(
            x='Date',
            y='Close'
        )
        c.encoding.y.scale = alt.Scale(domain=[df.Close.min()*0.95, df.Close.max()*1.05])
        line = alt.Chart(pd.DataFrame({'Close': selection.strike_short.to_list()})).mark_rule().encode(y='Close', color = alt.value("#FF0000"))
        st.header("\nPrice Chart (Red line indicating short strike)")
        st.altair_chart((c + line).interactive(), use_container_width=True)
    with tab3:
        px = px_screener(config)
        st.dataframe(px.sort_values(by='percentile',ascending=True))
    print("--- %s seconds ---" % (time.time() - start_time))
    st.code("Output refreshed --- %s seconds ---" % round(time.time() - start_time,4))