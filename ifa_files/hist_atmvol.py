import refinitiv.dataplatform as rdp
import pandas as pd
import numpy as np
from ifa_files.session import *
from datetime import datetime, timedelta
import streamlit as st
'''
# code for searching for ATM IV RICs (there might be multiple RICS)
response = rdp.search(
    query = 'SPYATMIV*',
    select = 'RIC')
'''
# Get 30 day ATM Put IV (should be same as call)
@st.cache_data()
def get_historical_iv(list_,period=250):
    sdate = str(datetime.strftime(datetime.now() - timedelta(period), '%Y%m%d'))
    edate = str(datetime.strftime(datetime.now(), '%Y%m%d'))
    atm_vol = rdp.get_data(
        ["{}ATMIV.U".format(sym) for sym in list_],
        ['TR.30DAYATTHEMONEYIMPLIEDVOLATILITYINDEXFORPUTOPTIONS.Date','TR.30DAYATTHEMONEYIMPLIEDVOLATILITYINDEXFORPUTOPTIONS'],
        {'SDate':sdate,'EDate':edate,'Frq':'D'})
    atm_vol.columns = ['sym','date','iv']
    atm_vol.date = atm_vol.date.apply(lambda x: x[0:10])
    atm_vol.date = pd.to_datetime(atm_vol.date)
    atm_vol.iv = atm_vol.iv.astype(float)
    atm_vol.sym = atm_vol.sym.apply(lambda x: x.replace("ATMIV.U", ""))
    return atm_vol
