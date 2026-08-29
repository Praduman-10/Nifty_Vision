import streamlit as st
from streamlit_autorefresh import st_autorefresh
from app_sqlite_patch import load_for_dashboard

st.set_page_config(page_title='Nifty Vision', page_icon='◈', layout='wide')
st.title('Nifty Vision')
st.caption('SQLite-first market data engine')
FRAMES=['1 min','3 min','5 min','15 min','30 min','1 hour','1 day']
frame=st.sidebar.selectbox('TIMEFRAME', FRAMES, index=2)
limit=st.sidebar.slider('CANDLES',50,2000,500,50)
st_autorefresh(interval=30000,key='nv_refresh')
try:
    df, source=load_for_dashboard(frame, limit)
    if df.empty:
        st.info('SQLite is ready but has no stored candles for this timeframe yet. Run the historical backfill.')
    else:
        st.metric('Stored candles', f'{len(df):,}')
        st.caption(f'Data source: {source}')
        st.dataframe(df, use_container_width=True, hide_index=True)
except Exception as exc:
    st.error(f'Market data failed: {type(exc).__name__}: {exc}')
