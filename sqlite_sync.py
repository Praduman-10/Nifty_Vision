import os
from datetime import date, timedelta
import requests
import pandas as pd
from database import upsert_candles, latest_timestamp

TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')
KEY = 'NSE_INDEX|Nifty 50'
TIMEFRAMES = {'1m': ('minutes',1), '3m': ('minutes',3), '5m': ('minutes',5), '15m': ('minutes',15), '30m': ('minutes',30), '1h': ('hours',1), '1d': ('days',1)}

def sync_timeframe(name, lookback_days=7):
    unit, interval = TIMEFRAMES[name]
    latest = latest_timestamp(KEY, f'{unit}_{interval}')
    start = pd.Timestamp(latest).date() if latest else date.today() - timedelta(days=lookback_days)
    end = date.today()
    url = f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{end:%Y-%m-%d}/{start:%Y-%m-%d}'
    r = requests.get(url, headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}, timeout=30)
    r.raise_for_status()
    rows = r.json().get('data',{}).get('candles',[])
    if not rows: return 0
    df = pd.DataFrame(rows, columns=['ts','open','high','low','close','volume','oi'])
    df.ts = pd.to_datetime(df.ts, utc=True)
    for c in ['open','high','low','close','volume','oi']: df[c] = pd.to_numeric(df[c], errors='coerce')
    return upsert_candles(df, KEY, f'{unit}_{interval}')
