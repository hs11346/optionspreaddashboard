from vectorised_load_data import *
import time
import altair as alt
import datetime
from ifa_files.hist_atmvol import get_historical_iv
from ifa_files.plotting_helper import *
from ifa_files.eti_surfaces import get_surface
import refinitiv.dataplatform as rdp

st.set_page_config(layout="wide")
'''
Streamlit Dashboard for hosting CBOE 
'''
def get_config():
    config = pd.read_csv('config.csv')
    return config.Tickers.to_list(), config

@st.cache_data(ttl=3600) # reload cache every 3600 seconds
def load_data():
    output_time = datetime.datetime.now(datetime.timezone.utc)# Record the time of scrapping the option data
    freeze_support()
    put = PCS_screener(list_, max_strike_width=5, min_dte=0, max_dte=50, fees=0.1, min_dist=0, min_bid=0.2)
    freeze_support()
    call = CCS_screener(list_, max_strike_width=5, min_dte=0, max_dte=50, fees=0.1, min_dist=0, min_bid=0.2)
    return put, call, output_time
@st.cache_data()
def yfinance_hist(option):
    return yf.download(option, interval='1d', period='1y')
if __name__=="__main__":
    start_time = time.time()
    #1204.6977639198303 seconds (unvectorised)
    #118.43037843704224 seconds (vectorised)
    st.title('Option Spread Monitor')
    list_, config = get_config()
    px_df = px_screener(config)
    put, call, output_time = load_data()
    put = put[(put.min_vol > 1) & (put.min_oi > 1)]
    call = call[(call.min_vol > 1) & (call.min_oi > 1)]
    st.title('Welcome to the CBOE Option Vertical Spread Monitor v4.0')
    st.write("Scrapped time (delayed quotes 10-15 min)")
    st.write(output_time)
    st.write('Integrated with Refinitiv Data Platform')
    st.info('**Data Analyst: [@hs11346](https://github.com/hs11346)**', icon="💡")
    option = st.sidebar.selectbox(
        'Ticker',
        list_)
    atm_vol = get_historical_iv(list_)
    max_width = st.sidebar.slider('Max Width', 0, 5, 3, 1)
    max_dte = st.sidebar.slider('Max DTE', 0, 50, 30, 1)
    min_dist = st.sidebar.slider('Min Distance', 0.1, 3.0, 1.1, 0.1)
    min_bid = st.sidebar.slider('Min bid', 0.01, 0.5, 0.2, 0.01)
    if st.sidebar.button('Reset cache'):
        st.cache_data.clear()
    tab0, tab1, tab2, tab3 = st.tabs(['Overview',"PCS", "CCS", 'Underlyings'])
    with tab0:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('Overview for Put Credit Spreads')
            overview_puts = alt.Chart(put.loc[(put.width <= max_width) & (put.dte <= max_dte) & (put.ATM_dist >= min_dist) & (put.bid >= min_bid)]).mark_point().encode(
                x='bid',
                y='ATM_dist',
                color = 'underlying'
            )
            st.altair_chart(overview_puts.interactive(), use_container_width=True)
        with col2:
            st.markdown('Overview for Call Credit Spreads')
            overview_calls = alt.Chart(call.loc[
                                          (call.width <= max_width) & (call.dte <= max_dte) & (call.ATM_dist >= min_dist) & (
                                                      call.bid >= min_bid)]).mark_point().encode(
                x='bid',
                y='ATM_dist',
                color='underlying'
            )
            st.altair_chart(overview_calls.interactive(), use_container_width=True)
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
        st.header("\nRisk-Reward plot")
        s = alt.Chart(filtered_put[['bid','ATM_dist','dte']]).mark_point().encode(
            x='bid',
            y='ATM_dist',
            color = 'dte'
        )
        st.altair_chart(s.interactive(), use_container_width=True)

        vol = alt.Chart(atm_vol[atm_vol.sym == option][['date','iv']]).mark_line().encode(
            x='date',
            y='iv'
        )
        c.encoding.y.scale = alt.Scale(domain=[atm_vol.iv.min() * 0.95, atm_vol.iv.max() * 1.05])
        st.header("\nHistorical 30 day implied volatility")
        st.altair_chart(vol.interactive(), use_container_width=True)

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
        st.header("\nRisk-Reward plot")
        s = alt.Chart(filtered_call[['bid','ATM_dist','dte']]).mark_point().encode(
            x='bid',
            y='ATM_dist',
            color = 'dte'
        )
        st.altair_chart(s.interactive(), use_container_width=True)
        vol = alt.Chart(atm_vol[atm_vol.sym == option][['date', 'iv']]).mark_line().encode(
            x='date',
            y='iv'
        )
        c.encoding.y.scale = alt.Scale(domain=[atm_vol.iv.min() * 0.95, atm_vol.iv.max() * 1.05])
        st.header("\nHistorical 30 day implied volatility")
        st.altair_chart(vol.interactive(), use_container_width=True)
    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            px = px_screener(config)
            #st.dataframe(px.sort_values(by='percentile',ascending=True))
            base = alt.Chart(px).encode(
                x='rsi',
                y="Tickers:O",
                text='rsi',
                #color = alt.condition(alt.datum['rsi'] > 70,alt.value('darkred'),alt.value('lightgreen'))
            )
            st.altair_chart((base.mark_bar() + base.mark_text(align='left', dx=2)).interactive(), use_container_width=True)
        with col2:
            base = alt.Chart(px).encode(
                x='percentile',
                y="Tickers:O",
                text='percentile')
            st.altair_chart((base.mark_bar() + base.mark_text(align='left', dx=2)).interactive(), use_container_width=True)
        st.pyplot(plot_smile(get_surface() , 1))
        st.pyplot(plot_term_volatility(get_surface(), 1))
    print("--- %s seconds ---" % (time.time() - start_time))
    st.code("Output refreshed --- %s seconds ---" % round(time.time() - start_time,4))
