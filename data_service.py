import os
from datetime import date, timedelta
import pandas as pd
import requests
from database import load_candles, upsert_candles, latest_timestamp

try:
    import streamlit as st
    TOKEN = st.secrets.get('UPSTOX_ACCESS_TOKEN', os.getenv('UPSTOX_ACCESS_TOKEN', ''))
except Exception:
    TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')

KEY='NSE_INDEX|Nifty 50'
TIMEFRAMES={'1 min':('minutes',1),'3 min':('minutes',3),'5 min':('minutes',5),'15 min':('minutes',15),'30 min':('minutes',30),'1 hour':('hours',1),'1 day':('days',1)}

def _empty():
    return pd.DataFrame(columns=['ts','open','high','low','close','volume','oi'])

def _normalise(rows):
    if not rows:return _empty()
    d=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','oi']);d.ts=pd.to_datetime(d.ts,utc=True)
    for c in ['open','high','low','close','volume','oi']:d[c]=pd.to_numeric(d[c],errors='coerce')
    return d

def _last_market_date(d):
    while d.weekday()>=5:d-=timedelta(days=1)
    return d

def _fetch_history(unit,interval,start,end):
    end=_last_market_date(end)
    if start>end:return _empty()
    url=f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{end:%Y-%m-%d}/{start:%Y-%m-%d}'
    r=requests.get(url,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20);r.raise_for_status()
    return _normalise(r.json().get('data',{}).get('candles',[]))

def _fetch_intraday(unit,interval):
    url=f'https://api.upstox.com/v3/historical-candle/intraday/{KEY}/{unit}/{interval}'
    r=requests.get(url,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20);r.raise_for_status()
    return _normalise(r.json().get('data',{}).get('candles',[]))

def get_market_data(label,limit=500):
    unit,interval=TIMEFRAMES[label];key=f'{unit}_{interval}';cached=load_candles(KEY,key,limit)
    try:
        if not TOKEN:raise RuntimeError('UPSTOX_ACCESS_TOKEN is unavailable to data_service')
        end=_last_market_date(date.today())
        if label=='1 day':
            fresh=_fetch_history(unit,interval,end-timedelta(days=365),end)
        else:
            historical=_fetch_history(unit,interval,end-timedelta(days=2),end)
            intraday=_fetch_intraday(unit,interval)
            fresh=pd.concat([historical,intraday],ignore_index=True)
            if not fresh.empty:fresh=fresh.drop_duplicates(subset=['ts'],keep='last').sort_values('ts')
        if not fresh.empty:upsert_candles(fresh,KEY,key)
        data=load_candles(KEY,key,limit)
        return data,'LIVE UPSTOX + SQLITE'
    except Exception:
        if not cached.empty:return cached,'SQLITE CACHE'
        raise
