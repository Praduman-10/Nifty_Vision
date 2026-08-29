import streamlit as st
from datetime import date, timedelta
from historical_loader import fetch_chunk

KEY='NSE_INDEX|Nifty 50'

def run_one_week(start,end,timeframe):
    unit,interval=('days',1) if timeframe=='1d' else ('minutes',5)
    return fetch_chunk(start,end,unit,interval)

st.set_page_config(page_title='Nifty Vision Backfill Runner',layout='wide')
st.title('Nifty Vision — Backfill Runner')
st.write('Run one small historical chunk at a time. This keeps the process resumable and avoids a large Upstox request.')
frame=st.selectbox('Timeframe',['1d','5m'])
start=st.date_input('Chunk start',date.today()-timedelta(days=7))
end=st.date_input('Chunk end',date.today())
if st.button('Load this chunk'):
    if end<start: st.error('End date must be on or after start date.')
    else:
        try:
            n=run_one_week(start,end,frame)
            st.success(f'Loaded {n:,} {frame} candles into SQLite.')
        except Exception as e:
            st.error(f'Backfill failed: {type(e).__name__}: {e}')
st.caption('Repeat with earlier date ranges to build the year gradually. Existing candles are safely upserted.')
