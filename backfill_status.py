import os
from datetime import date
import streamlit as st
from sqlite_status import status

st.set_page_config(page_title='Nifty Vision Backfill', layout='wide')
st.title('Nifty Vision — Historical Data')
st.caption('SQLite backfill monitor')

rows = status()
if rows:
    st.dataframe([{'timeframe': r[0], 'candles': r[1], 'first': r[2], 'last': r[3]} for r in rows], use_container_width=True, hide_index=True)
else:
    st.info('No historical candles are stored yet.')

st.markdown('### Backfill plan')
st.write(f'Current year: {date.today().year}')
st.write('Initial load: NIFTY 50 5-minute + 1-day candles, downloaded in small resumable chunks.')
st.write('After initial load: incremental sync only; existing candles are not downloaded again.')

if not os.getenv('UPSTOX_ACCESS_TOKEN'):
    st.warning('UPSTOX_ACCESS_TOKEN must be available to the runtime before a backfill can run.')
else:
    st.success('Upstox token is available to the runtime. Run backfill.py from a persistent job/runtime to populate SQLite.')
