import os
from datetime import date, timedelta
from urllib.parse import quote
import pandas as pd
import requests
from database import load_candles, upsert_candles

try:
    import streamlit as st
    TOKEN = st.secrets.get('UPSTOX_ACCESS_TOKEN', os.getenv('UPSTOX_ACCESS_TOKEN', ''))
except Exception:
    TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')

KEY='NSE_INDEX|Nifty 50'
ENCODED_KEY=quote(KEY, safe='')
TIMEFRAMES={'1 min':('minutes',1),'3 min':('minutes',3),'5 min':('minutes',5),'15 min':('minutes',15),'30 min':('minutes',30),'1 hour':('hours',1),'1 day':('days',1)}

def _empty(): return pd.DataFrame(columns=['ts','open','high','low','close','volume','oi'])

def _normalise(rows):
    if not rows:return _empty()
    d=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','oi'])
    d['ts']=pd.to_datetime(d['ts'],utc=True,errors='coerce')
    for c in ['open','high','low','close','volume','oi']:d[c]=pd.to_numeric(d[c],errors='coerce')
    return d.dropna(subset=['ts','open','high','low','close']).sort_values('ts').drop_duplicates('ts').reset_index(drop=True)

def _last_market_date(d):
    while d.weekday()>=5:d-=timedelta(days=1)
    return d

def _request(url):
    if not TOKEN: raise RuntimeError('UPSTOX_ACCESS_TOKEN is unavailable to data_service')
    r=requests.get(url,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20)
    if r.status_code!=200: raise RuntimeError(f'Upstox HTTP {r.status_code}: {r.text[:300]}')
    return _normalise(r.json().get('data',{}).get('candles',[]))

def _fetch_history(unit,interval,start,end):
    end=_last_market_date(end)
    if start>end:return _empty()
    url=f'https://api.upstox.com/v3/historical-candle/{ENCODED_KEY}/{unit}/{interval}/{end:%Y-%m-%d}/{start:%Y-%m-%d}'
    return _request(url)

def _fetch_intraday_1m():
    url=f'https://api.upstox.com/v3/historical-candle/intraday/{ENCODED_KEY}/minutes/1'
    return _request(url)

def _resample_1m(d, label):
    if d.empty:return d
    if label=='1 min':return d
    rule={'3 min':'3min','5 min':'5min','15 min':'15min','30 min':'30min','1 hour':'1h'}[label]
    x=d.set_index('ts').sort_index()
    out=x.resample(rule,origin='start_day',offset='15min').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum','oi':'last'}).dropna(subset=['open','high','low','close']).reset_index()
    return out

def get_market_data(label,limit=500):
    unit,interval=TIMEFRAMES[label];key=f'{unit}_{interval}';cached=load_candles(KEY,key,limit)
    try:
        end=_last_market_date(date.today())
        if label=='1 day':
            fresh=_fetch_history('days',1,end-timedelta(days=365),end)
        else:
            # Upstox V3 supports custom intraday intervals, but using the 1-minute
            # feed as the source and aggregating locally makes the dashboard robust
            # across 3/5/15/30-minute and hourly views.
            one_min=_fetch_intraday_1m()
            if one_min.empty:
                one_min=_fetch_history('minutes',1,end-timedelta(days=7),end)
            fresh=_resample_1m(one_min,label)
        if fresh.empty: raise RuntimeError(f'Upstox returned no usable candles for {label}.')
        upsert_candles(fresh,KEY,key)
        data=load_candles(KEY,key,limit)
        if data.empty: raise RuntimeError(f'Candles were fetched but could not be loaded from SQLite for {label}.')
        return data,'LIVE UPSTOX + SQLITE'
    except Exception:
        if not cached.empty:return cached,'SQLITE CACHE'
        raise
