import time
from datetime import date, timedelta
import requests
import pandas as pd
from database import upsert_candles

TOKEN = __import__('os').environ.get('UPSTOX_ACCESS_TOKEN','')
KEY = 'NSE_INDEX|Nifty 50'


def fetch_chunk(start_date, end_date, unit='minutes', interval=5):
    url = f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{end_date:%Y-%m-%d}/{start_date:%Y-%m-%d}'
    r = requests.get(url, headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}, timeout=30)
    r.raise_for_status()
    rows = r.json().get('data',{}).get('candles',[])
    if not rows: return 0
    df = pd.DataFrame(rows, columns=['ts','open','high','low','close','volume','oi'])
    df.ts = pd.to_datetime(df.ts, utc=True)
    for c in ['open','high','low','close','volume','oi']: df[c] = pd.to_numeric(df[c], errors='coerce')
    return upsert_candles(df, KEY, f'{unit}_{interval}')


def backfill_year(year, unit='minutes', interval=5, chunk_days=7, pause_seconds=0.35):
    start = date(year,1,1); end = min(date(year,12,31), date.today())
    total = 0; cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days-1), end)
        total += fetch_chunk(cursor, chunk_end, unit, interval)
        cursor = chunk_end + timedelta(days=1)
        time.sleep(pause_seconds)
    return total

if __name__ == '__main__':
    print('Starting NIFTY 50 SQLite backfill for the current year...')
    print('5-minute candles:', backfill_year(date.today().year, 'minutes', 5))
