import os
from datetime import date, timedelta
import pandas as pd
import requests
from database import load_candles, upsert_candles, latest_timestamp

TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')
KEY = 'NSE_INDEX|Nifty 50'
TIMEFRAMES = {'1 min':('minutes',1),'3 min':('minutes',3),'5 min':('minutes',5),'15 min':('minutes',15),'30 min':('minutes',30),'1 hour':('hours',1),'1 day':('days',1)}


def _last_market_date(d):
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _fetch(unit, interval, start, end):
    end = _last_market_date(end)
    if start > end:
        return pd.DataFrame(columns=['ts','open','high','low','close','volume','oi'])
    url=f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{end:%Y-%m-%d}/{start:%Y-%m-%d}'
    r=requests.get(url,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=30)
    r.raise_for_status()
    rows=r.json().get('data',{}).get('candles',[])
    if not rows:return pd.DataFrame(columns=['ts','open','high','low','close','volume','oi'])
    d=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','oi'])
    d.ts=pd.to_datetime(d.ts,utc=True)
    for c in ['open','high','low','close','volume','oi']:d[c]=pd.to_numeric(d[c],errors='coerce')
    return d


def get_market_data(label, limit=500):
    unit,interval=TIMEFRAMES[label]
    key=f'{unit}_{interval}'
    cached=load_candles(KEY,key,limit)
    latest=latest_timestamp(KEY,key)
    end=_last_market_date(date.today())
    try:
        # Daily candles are cheap and have a much larger API range, so seed/fill
        # the full recent year even if a few daily rows already exist.
        if label=='1 day':
            start=end-timedelta(days=365)
        else:
            start=pd.Timestamp(latest).date() if latest else end-timedelta(days=7)
        fresh=_fetch(unit,interval,start,end)
        if not fresh.empty:
            upsert_candles(fresh,KEY,key)
        data=load_candles(KEY,key,limit)
        return data,'SQLITE + UPSTOX'
    except Exception:
        if not cached.empty:return cached,'SQLITE CACHE'
        raise
