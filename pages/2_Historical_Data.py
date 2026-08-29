import streamlit as st
from datetime import date, timedelta
from historical_loader import fetch_chunk
from sqlite_status import status

st.set_page_config(page_title='Nifty Vision Historical Data',layout='wide')
st.title('Historical Data')
st.caption('Build the SQLite history gradually — 1D first, then 5m.')

rows=status()
if rows:
    st.dataframe([{'timeframe':r[0],'candles':r[1],'first':r[2],'last':r[3]} for r in rows],use_container_width=True,hide_index=True)
else: st.info('SQLite currently has no candles.')

st.divider()
frame=st.selectbox('Load timeframe',['1d','5m'])
end=date.today(); default_start=end-timedelta(days=7)
start=st.date_input('Start date',default_start)
finish=st.date_input('End date',end)
if st.button('Load selected range',type='primary'):
    if finish<start: st.error('End date must be after start date.')
    else:
        unit,interval=('days',1) if frame=='1d' else ('minutes',5)
        try:
            n=fetch_chunk(start,finish,unit,interval)
            st.success(f'Loaded {n:,} {frame} candles into SQLite. Refresh this page to see the updated counts.')
        except Exception as e: st.error(f'Upstox backfill failed: {type(e).__name__}: {e}')

st.info('For a full-year load, repeat the operation in small date ranges. Existing candles are upserted, so repeating a range will not create duplicates.')
