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
    for short_index in df.index.to_list(): # Loop for all combinations of put vertical spreads
        for long_index in df.index.to_list():
            if abs(df.iloc[short_index].strike - df.iloc[long_index].strike) <= max_strike_width and \
                    df.iloc[short_index].exDate == df.iloc[long_index].exDate and \
                    df.iloc[short_index].strike > df.iloc[long_index].strike and \
                    df.iloc[short_index].dte <= max_dte and df.iloc[short_index].dte >= min_dte: # Specify maximum strike width and same exDate
                dict_ = {"symbol":df.iloc[long_index].symbol+"-"+df.iloc[short_index].symbol\
                                    ,"width":df.iloc[short_index].strike - df.iloc[long_index].strike,
                         "short_strike":df.iloc[short_index].strike, "long_strike":df.iloc[long_index].strike,\
                         "bid":df.iloc[short_index].bid-df.iloc[long_index].ask,\
                                  "ask":df.iloc[short_index].ask-df.iloc[long_index].bid, \
                         "delta": -df.iloc[short_index].delta + df.iloc[long_index].delta, \
                         "vega": -df.iloc[short_index].vega + df.iloc[long_index].vega, \
                         "theta": -df.iloc[short_index].theta + df.iloc[long_index].theta, \
                         'min_vol':min(df.iloc[short_index].volume,df.iloc[long_index].volume),\
                                  'min_oi':min(df.iloc[short_index].OI,df.iloc[long_index].OI),\
                                  'exDate':df.iloc[short_index].exDate,\
                                  'dte':df.iloc[short_index].dte,'underlying':underlying}
                spread_df = pd.concat([spread_df,pd.DataFrame(dict_, index = [0])], ignore_index=True)
    if spread_df.empty:
        print('No combinations for {}'.format(underlying))
        return spread_df
    # Risk-reward ratio, Reward adjusted down by fees
    spread_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    spread_df.dropna(inplace = True)
    spread_df['RR_ratio'] = ((spread_df.bid + spread_df.ask - fees * 2) / (2 * spread_df.width))*100
    spread_df = spread_df[spread_df['RR_ratio'] > 0]
    #ATM distance is the % difference between strike and underlying price divided by the return volatility (adjusted by dte)
    spread_df['ATM_dist'] = (abs(spread_df['short_strike'] - current_price)/current_price)/(underlying_vol(underlying, days=60) * np.sqrt(spread_df.dte))
    spread_df = spread_df[spread_df.ATM_dist >= min_dist]
    # Min bid
    spread_df = spread_df[spread_df.bid >= min_bid]
    # RR_ratio / ATM_dist
    spread_df['dist_RR'] = spread_df.ATM_dist/spread_df.RR_ratio
    spread_df[['min_vol', 'min_oi']] = spread_df[['min_vol', 'min_oi']].astype(int)
    spread_df = spread_df.sort_values(by='dist_RR', ascending=False)
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
    for short_index in df.index.to_list(): # Loop for all combinations of put vertical spreads
        for long_index in df.index.to_list():
            if abs(df.iloc[short_index].strike - df.iloc[long_index].strike) <= max_strike_width and \
                    df.iloc[short_index].exDate == df.iloc[long_index].exDate and \
                    df.iloc[short_index].strike < df.iloc[long_index].strike and \
                    df.iloc[short_index].dte <= max_dte and df.iloc[short_index].dte >= min_dte: # Specify maximum strike width and same exDate
                dict_ = {"symbol":df.iloc[long_index].symbol+"-"+df.iloc[short_index].symbol\
                                    ,"width":df.iloc[long_index].strike - df.iloc[short_index].strike,
                         "short_strike":df.iloc[short_index].strike, "long_strike":df.iloc[long_index].strike,\
                         "bid":df.iloc[short_index].bid-df.iloc[long_index].ask,\
                                  "ask":df.iloc[short_index].ask-df.iloc[long_index].bid, \
                         "delta": -df.iloc[short_index].delta + df.iloc[long_index].delta, \
                         "vega": -df.iloc[short_index].vega + df.iloc[long_index].vega, \
                         "theta": -df.iloc[short_index].theta + df.iloc[long_index].theta, \
                         'min_vol':min(df.iloc[short_index].volume,df.iloc[long_index].volume),\
                                  'min_oi':min(df.iloc[short_index].OI,df.iloc[long_index].OI),\
                                  'exDate':df.iloc[short_index].exDate,\
                                  'dte':df.iloc[short_index].dte,'underlying':underlying}
                spread_df = pd.concat([spread_df,pd.DataFrame(dict_, index = [0])], ignore_index=True)
    if spread_df.empty:
        print('No combinations for {}'.format(underlying))
        return spread_df
    # Risk-reward ratio, Reward adjusted down by fees
    spread_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    spread_df.dropna(inplace=True)
    spread_df['RR_ratio'] = ((spread_df.bid + spread_df.ask - fees * 2) / (2 * spread_df.width))*100
    spread_df = spread_df[spread_df['RR_ratio'] > 0]
    #ATM distance is the % difference between strike and underlying price divided by the return volatility (adjusted by dte)
    spread_df['ATM_dist'] = (abs(spread_df['short_strike'] - current_price)/current_price)/(underlying_vol(underlying, days=60) * np.sqrt(spread_df.dte))
    spread_df = spread_df[spread_df.ATM_dist >= min_dist]
    # Min bid
    spread_df = spread_df[spread_df.bid >= min_bid]
    # RR_ratio / ATM_dist
    spread_df['dist_RR'] = spread_df.ATM_dist/spread_df.RR_ratio
    spread_df.fillna(0,inplace=True)
    spread_df[['min_vol', 'min_oi']] = spread_df[['min_vol', 'min_oi']].astype(int)
    spread_df = spread_df.sort_values(by='dist_RR', ascending=False)
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






