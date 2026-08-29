import streamlit as st
import pandas as pd
from database import load_candles, latest_timestamp, DB_PATH

st.set_page_config(page_title='Nifty Vision SQLite', layout='wide')
st.title('Nifty Vision — SQLite Data Layer')

TIMEFRAMES = {'5m': 'minutes_5', '1d': 'days_1', '1h': 'hours_1', '15m': 'minutes_15', '3m': 'minutes_3', '1m': 'minutes_1', '30m': 'minutes_30'}
frame = st.selectbox('Stored timeframe', list(TIMEFRAMES), index=0)
limit = st.slider('Rows to display', 50, 5000, 500, 50)

try:
    df = load_candles('NSE_INDEX|Nifty 50', TIMEFRAMES[frame], limit)
    if df.empty:
        st.info(f'No {frame} candles are stored yet. Run the backfill/sync process first.')
    else:
        st.metric('Stored candles shown', f'{len(df):,}')
        st.caption(f'Database: {DB_PATH.name} · Latest stored candle: {latest_timestamp("NSE_INDEX|Nifty 50", TIMEFRAMES[frame])}')
        st.dataframe(df, use_container_width=True, hide_index=True)
except Exception as exc:
    st.error(f'SQLite read failed: {type(exc).__name__}: {exc}')
