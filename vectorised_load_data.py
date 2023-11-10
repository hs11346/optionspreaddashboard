from urllib.request import urlopen
import json
from pandas import json_normalize
import pandas as pd
import numpy as np
import warnings
import streamlit as st
import datetime
from datetime import timedelta
from multiprocessing import Pool, freeze_support
from functools import partial
from scipy import stats
import yfinance as yf
import pandas_market_calendars as mcal

nyse = mcal.get_calendar('NYSE')
holidays = nyse.holidays()
holidays = list(holidays.holidays)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)
'''
Get data from CBOE link
Delayed data (around 10-15 min?), suitable for EOD or before market open analysis
'''

def get_current_price(symbol):
    ticker = yf.Ticker(symbol)
    todays_data = ticker.history(period='1d', interval = '1m')
    return todays_data['Close'][-1]
# Read CBOE option data
@st.cache_data()
def cboe_opx_chain(symbol):
    url = "https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json".format(symbol)
    response = urlopen(url)
    dict = json.loads(response.read())
    df = json_normalize(dict['data']['options'])
    # 1. Regex to extract the OCC Option Symbol
    pattern = r'[A-Z]{1,6}(\d{6})([CP])(\d+)'
    df[['exDate', 'CPFlag', 'strike']] = \
        df.option.str.extract(pattern, expand=True)
    df.exDate = pd.to_datetime(df.exDate, format='%y%m%d')
    df.strike = df.strike.astype(float) / 1000
    # 2. Rename columns to fit yfinance option chain
    df.rename(columns = {'option':'symbol','iv':'IV','open_interest':'OI'},inplace=True)
    df = df[['symbol', 'bid','ask','IV', 'OI',
       'volume', 'delta', 'gamma', 'theta','vega', 'theo','last_trade_price', 'last_trade_time',
       'prev_day_close', 'exDate', 'CPFlag', 'strike']]

    # 3. Get ITM flag
    current = get_current_price(symbol)
    def isITM(opx_px, type):
        if type == 'C':
            if opx_px > current:
                return False
            else:
                return True
        elif type == 'P':
            if opx_px > current:
                return True
            else:
                return False
    df['ITM'] = df.apply(lambda x: isITM(x.strike, x.CPFlag), axis =1)
    # 4. Get DTE
    df.exDate = df.exDate.dt.date
    df = df[df.strike.isnull() == False] # remove bizzare option symbols from which strike and exDate cannot be extracted
    # adjust datetime from HK timezone to US timezone
    assert df[df.exDate.isnull()].empty, "Expiration Date Null at {}".format(symbol)
    df['dte'] = df['exDate'].apply(lambda x: np.busday_count((datetime.datetime.today() - timedelta(hours = 12)).date(), x,holidays=holidays))
    return df

def underlying_vol(ticker, days=60):
    df = yf.download(ticker, interval='1d',period = '1y')
    df['Ret'] = (df['Adj Close'] / df['Adj Close'].shift(1))
    df['Volatility'] = df['Ret'].rolling(window=days).std() # unannualised
    return df.Volatility.iloc[-1]

def PCS_screener(list_,IsITM = False, max_strike_width = 4, min_dte = 0, max_dte = 40, fees = 0.1, min_dist = 0, min_bid = 0.1):
    '''
    Adapted to CBOE version
    '''

    with Pool() as pool: # New Version, multiprocessing
        x = pool.map(partial(put_credit_spread, IsITM = IsITM, max_strike_width = max_strike_width, min_dte = min_dte, max_dte = max_dte, fees = fees, min_dist = min_dist, min_bid = min_bid), list_)
    try:
        df = pd.concat(x)
        return df
    except ValueError:
        pass

def CCS_screener(list_,IsITM = False, max_strike_width = 4, min_dte = 0, max_dte = 40, fees = 0.1, min_dist = 0, min_bid = 0.1):
    with Pool() as pool:  # New Version, multiprocessing
        x = pool.map(partial(call_credit_spread, IsITM=IsITM, max_strike_width=max_strike_width,
                             min_dte=min_dte, max_dte=max_dte, fees=fees, min_dist=min_dist, min_bid=min_bid), list_)

    try:
        df = pd.concat(x)
        return df
    except ValueError:
        pass
def put_credit_spread(underlying, IsITM = False, max_strike_width = 4, min_dte = 0, max_dte = 30, fees = 0.1, min_dist = 0, min_bid = 0):
    # PCS -> Short higher strike, long lower strike; Fee structure based on two way fees, futu fees = $10 per contract ($0.1)
    # Moneyness is the minimum moneyness of option strikes for scanning
    df = cboe_opx_chain(underlying)
    current_price = get_current_price(underlying)
    df = df[df.ITM == IsITM][df.CPFlag == 'P'][(df.bid >= 0)|(df.ask >=0)] # Extract OTM Puts from chain with non-zero bid-ask
    spread_df = pd.DataFrame()
    df.reset_index(inplace=True, drop=True)
    merged_df = df.merge(df, on='exDate', suffixes=('_short', '_long'))
    spread_df = merged_df[
        (abs(merged_df.strike_short - merged_df.strike_long) <= max_strike_width) &
        (merged_df.strike_short > merged_df.strike_long) &
        (min_dte <= merged_df.dte_short) & (merged_df.dte_short <= max_dte)
        ].copy()
    spread_df['width'] = spread_df.strike_short - spread_df.strike_long
    spread_df['bid'] = spread_df.bid_short - spread_df.ask_long
    spread_df['ask'] = spread_df.ask_short - spread_df.bid_long
    spread_df['delta'] = -spread_df.delta_short + spread_df.delta_long
    spread_df['vega'] = -spread_df.vega_short + spread_df.vega_long
    spread_df['theta'] = -spread_df.theta_short + spread_df.theta_long

    spread_df['min_vol'] = spread_df[['volume_short', 'volume_long']].min(axis=1)
    spread_df['min_oi'] = spread_df[['OI_short', 'OI_long']].min(axis=1)

    spread_df['RR_ratio'] = ((spread_df.bid + spread_df.ask - fees * 2) / (2 * spread_df.width)) * 100

    spread_df['ATM_dist'] = (abs(spread_df.strike_short - current_price) / current_price) / (
                underlying_vol(underlying, days=60) * np.sqrt(spread_df.dte_short + 1))

    spread_df = spread_df[
        (spread_df['RR_ratio'] > 0) &
        (spread_df['ATM_dist'] >= min_dist) &
        (spread_df['bid'] >= min_bid)
        ][['width','strike_short','strike_long','bid','ask','delta','vega','min_vol','min_oi','RR_ratio','ATM_dist','exDate','dte_short']].rename(columns = {'dte_short':'dte'})

    spread_df['dist_RR'] = spread_df.ATM_dist / spread_df.RR_ratio
    spread_df[['min_vol', 'min_oi']] = spread_df[['min_vol', 'min_oi']].astype(int)

    spread_df = spread_df.sort_values(by='dist_RR', ascending=False)
    spread_df['underlying'] = underlying

    print("{} combinations found for {}".format(len(spread_df), underlying))
    return spread_df.round(2)


def call_credit_spread(underlying, IsITM = False, max_strike_width = 4, min_dte = 0, max_dte = 30, fees = 0.1, min_dist = 0, min_bid = 0):
    # CCS -> long higher strike, short lower strike; Fee structure based on two way fees, futu fees = $10 per contract ($0.1)
    # Moneyness is the minimum moneyness of option strikes for scanning
    df = cboe_opx_chain(underlying)
    current_price = get_current_price(underlying)
    df = df[df.ITM == IsITM][df.CPFlag == 'C'][(df.bid >= 0)|(df.ask >=0)] # Extract OTM Puts from chain with non-zero bid-ask
    spread_df = pd.DataFrame()
    df.reset_index(inplace=True, drop=True)
    merged_df = df.merge(df, on='exDate', suffixes=('_short', '_long'))
    spread_df = merged_df[
        (abs(merged_df.strike_short - merged_df.strike_long) <= max_strike_width) &
        (merged_df.strike_short < merged_df.strike_long) &
        (min_dte <= merged_df.dte_short) & (merged_df.dte_short <= max_dte)
        ].copy()
    spread_df['width'] = spread_df.strike_long - spread_df.strike_short
    spread_df['bid'] = spread_df.bid_short - spread_df.ask_long
    spread_df['ask'] = spread_df.ask_short - spread_df.bid_long
    spread_df['delta'] = -spread_df.delta_short + spread_df.delta_long
    spread_df['vega'] = -spread_df.vega_short + spread_df.vega_long
    spread_df['theta'] = -spread_df.theta_short + spread_df.theta_long

    spread_df['min_vol'] = spread_df[['volume_short', 'volume_long']].min(axis=1)
    spread_df['min_oi'] = spread_df[['OI_short', 'OI_long']].min(axis=1)

    spread_df['RR_ratio'] = ((spread_df.bid + spread_df.ask - fees * 2) / (2 * spread_df.width)) * 100

    spread_df['ATM_dist'] = (abs(spread_df.strike_short - current_price) / current_price) / (
            underlying_vol(underlying, days=60) * np.sqrt(spread_df.dte_short + 1))

    spread_df = spread_df[
        (spread_df['RR_ratio'] > 0) &
        (spread_df['ATM_dist'] >= min_dist) &
        (spread_df['bid'] >= min_bid)
        ][['width','strike_short','strike_long','bid','ask','delta','vega','min_vol','min_oi','RR_ratio','ATM_dist','exDate','dte_short']].rename(columns = {'dte_short':'dte'})

    spread_df['dist_RR'] = spread_df.ATM_dist / spread_df.RR_ratio
    spread_df[['min_vol', 'min_oi']] = spread_df[['min_vol', 'min_oi']].astype(int)

    spread_df = spread_df.sort_values(by='dist_RR', ascending=False)
    spread_df['underlying'] = underlying
    print("{} combinations found for {}".format(len(spread_df), underlying))
    return spread_df.round(2)

def rsi_value(underlying, upper = 70, lower = 30):
    symbol = yf.Ticker(underlying)
    df = symbol.history(interval="1d", period="1mo", auto_adjust=True).tail(30)
    change = df["Close"].diff()
    change.dropna(inplace=True)
    # Create two copies of the Closing price Series
    change_up = change.copy()
    change_down = change.copy()
    change_up[change_up < 0] = 0
    change_down[change_down > 0] = 0
    change.equals(change_up + change_down)
    avg_up = change_up.rolling(14).mean()
    avg_down = change_down.rolling(14).mean().abs()
    rsi = 100 * avg_up / (avg_up + avg_down)
    # Take a look at the 20 oldest datapoints
    value = rsi.iloc[-1]
    if value >= upper:
        value = 1
    elif value <= lower:
        value = -1
    else:
        value = 0
    return value

def one_year_percentile(underlying):
    symbol = yf.Ticker(underlying)
    df = symbol.history(interval="1d", period="1y", auto_adjust=True)
    current = df.Close.iloc[-1]
    return stats.percentileofscore(df['Close'], current, kind='mean')

@st.cache_data()
def px_screener(df, upper = 70, lower = 30):
    df['rsi'] = df.Tickers.apply(lambda x: rsi_value(x, upper = upper, lower= lower))
    df['percentile'] = df.Tickers.apply(lambda x: one_year_percentile(x))
    return df






