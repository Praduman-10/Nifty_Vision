import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).with_name('nifty_vision.db')


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute('''CREATE TABLE IF NOT EXISTS candles (
        instrument TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        ts TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume REAL,
        oi REAL,
        PRIMARY KEY (instrument, timeframe, ts)
    )''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(instrument, timeframe, ts)')
    con.commit()
    return con


def upsert_candles(df, instrument, timeframe):
    if df is None or df.empty:
        return 0
    con = connect()
    rows = []
    for _, r in df.iterrows():
        rows.append((instrument, timeframe, pd.Timestamp(r.ts).isoformat(), float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume) if pd.notna(r.volume) else None, float(r.oi) if pd.notna(r.oi) else None))
    con.executemany('''INSERT OR REPLACE INTO candles
        (instrument,timeframe,ts,open,high,low,close,volume,oi)
        VALUES (?,?,?,?,?,?,?,?,?)''', rows)
    con.commit(); con.close()
    return len(rows)


def load_candles(instrument, timeframe, limit=None):
    con = connect()
    sql = 'SELECT ts,open,high,low,close,volume,oi FROM candles WHERE instrument=? AND timeframe=? ORDER BY ts DESC'
    params = [instrument, timeframe]
    if limit:
        sql += ' LIMIT ?'; params.append(int(limit))
    df = pd.read_sql_query(sql, con, params=params)
    con.close()
    if df.empty:
        return df
    df.ts = pd.to_datetime(df.ts, utc=True)
    return df.sort_values('ts').reset_index(drop=True)


def latest_timestamp(instrument, timeframe):
    con = connect()
    row = con.execute('SELECT MAX(ts) FROM candles WHERE instrument=? AND timeframe=?', (instrument, timeframe)).fetchone()
    con.close()
    return row[0] if row and row[0] else None
