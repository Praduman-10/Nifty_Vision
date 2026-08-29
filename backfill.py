import os
import time
from datetime import date, timedelta
import requests
import pandas as pd
from database import upsert_candles, latest_timestamp

TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')
KEY = 'NSE_INDEX|Nifty 50'

TIMEFRAMES = {
    '1m': ('minutes', 1),
    '3m': ('minutes', 3),
    '5m': ('minutes', 5),
    '15m': ('minutes', 15),
    '30m': ('minutes', 30),
    '1h': ('hours', 1),
    '1d': ('days', 1),
}


def fetch_chunk(start_date, end_date, unit, interval):
    url = f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{end_date:%Y-%m-%d}/{start_date:%Y-%m-%d}'
    r = requests.get(url, headers={'Accept': 'application/json', 'Authorization': f'Bearer {TOKEN}'}, timeout=30)
    r.raise_for_status()
    rows = r.json().get('data', {}).get('candles', [])
    if not rows:
        return 0
    df = pd.DataFrame(rows, columns=['ts','open','high','low','close','volume','oi'])
    df.ts = pd.to_datetime(df.ts, utc=True)
    for c in ['open','high','low','close','volume','oi']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return upsert_candles(df, KEY, f'{unit}_{interval}')


def backfill_year(year=None, selected=('5m','1d'), chunk_days=7, pause=0.5):
    if not TOKEN:
        raise RuntimeError('UPSTOX_ACCESS_TOKEN is not set.')
    year = year or date.today().year
    end = min(date(year, 12, 31), date.today())
    total = 0
    for name in selected:
        unit, interval = TIMEFRAMES[name]
        step = chunk_days if unit == 'minutes' else (30 if unit == 'hours' else 365)
        cursor = date(year, 1, 1)
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=step - 1), end)
            try:
                count = fetch_chunk(cursor, chunk_end, unit, interval)
                total += count
                print(f'{name}: {cursor} -> {chunk_end}: {count} candles')
            except requests.HTTPError as exc:
                print(f'{name}: {cursor} -> {chunk_end} failed: {exc}')
            cursor = chunk_end + timedelta(days=1)
            time.sleep(pause)
    return total


if __name__ == '__main__':
    backfill_year(selected=('5m','1d'))
