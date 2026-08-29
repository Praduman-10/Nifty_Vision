import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from data_service import get_market_data, TIMEFRAMES

st.set_page_config(page_title='Nifty Vision', page_icon='◈', layout='wide')
st_autorefresh(interval=30000, key='nv_live')

st.markdown('''<style>
.stApp{background:#050505;color:#f5f5f5}.block-container{max-width:1800px;padding-top:2rem!important}
[data-testid="stSidebar"]{background:#090909;border-right:1px solid #252525}
.title{font-size:2.5rem;font-weight:950;letter-spacing:-2px}.muted{color:#777;font-size:.75rem}
.card{background:#0d0d0d;border:1px solid #292929;border-radius:14px;padding:14px}.label{font-size:.62rem;color:#777;font-weight:800;letter-spacing:1.4px}.value{font-size:1.25rem;font-weight:900;margin-top:5px}
.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:#0b0b0b;border:1px solid #252525;border-radius:15px;padding:16px}
.section{font-size:.7rem;font-weight:900;letter-spacing:1.3px;text-transform:uppercase;margin-bottom:10px}
</style>''', unsafe_allow_html=True)

st.sidebar.markdown('**NIFTY VISION**')
frame=st.sidebar.selectbox('TIMEFRAME', list(TIMEFRAMES), index=2)
visible=st.sidebar.slider('VISIBLE CANDLES', 100, 2000, 500, 50)
ema=st.sidebar.checkbox('EMA 9 / 20 / 50', True)
vwap=st.sidebar.checkbox('VWAP', True)
rsi_on=st.sidebar.checkbox('RSI', True)

try:
    data,source=get_market_data(frame, max(visible,500))
except Exception as e:
    st.error(f'Data feed failed: {type(e).__name__}: {e}')
    st.stop()

if data.empty:
    st.warning('SQLite has no candles yet. Run the historical backfill first.')
    st.stop()

d=data.tail(visible).copy()
d['ema9']=d.close.ewm(span=9,adjust=False).mean();d['ema20']=d.close.ewm(span=20,adjust=False).mean();d['ema50']=d.close.ewm(span=50,adjust=False).mean()
tp=(d.high+d.low+d.close)/3;vol=pd.to_numeric(d.volume,errors='coerce').fillna(0)
d['session']=d.ts.dt.date;pv=tp*vol;cv=pv.groupby(d.session).cumsum();vv=vol.groupby(d.session).cumsum();d['vwap']=cv/vv.replace(0,pd.NA)
delta=d.close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();d['rsi']=100-100/(1+gain/loss.replace(0,pd.NA))

last=d.iloc[-1];prev=d.iloc[-2] if len(d)>1 else last;chg=last.close-prev.close;pct=chg/prev.close*100
bias='BULLISH' if last.close>last.ema20 and last.ema9>last.ema20 else ('BEARISH' if last.close<last.ema20 and last.ema9<last.ema20 else 'MIXED')
bias_cls='green' if bias=='BULLISH' else 'red' if bias=='BEARISH' else 'amber'

st.markdown('<div class="muted">NIFTY 50 • PRICE ACTION</div><div class="title">Nifty Vision</div>',unsafe_allow_html=True)
st.markdown(f'<div class="muted">SQLite-first • {frame} • {source} • latest {last.ts}</div>',unsafe_allow_html=True)
st.divider()
cols=st.columns(5)
items=[('NIFTY',f'{last.close:,.2f}',f'{chg:+.2f} ({pct:+.2f}%)',''),('BIAS',bias,'EMA structure',bias_cls),('RSI 14',f'{last.rsi:.1f}','Momentum',''),('VWAP',f'{last.vwap:,.2f}' if pd.notna(last.vwap) else 'N/A','Session VWAP',''),('CANDLES',f'{len(d):,}',source,'')]
for c,(a,b,x,cl) in zip(cols,items):c.markdown(f'<div class="card"><div class="label">{a}</div><div class="value {cl}">{b}</div><div class="muted">{x}</div></div>',unsafe_allow_html=True)

f=go.Figure(go.Candlestick(x=d.ts,open=d.open,high=d.high,low=d.low,close=d.close,name='NIFTY',increasing_line_color='#00e676',decreasing_line_color='#ff5252'))
if ema:
    for col,name in [('ema9','EMA 9'),('ema20','EMA 20'),('ema50','EMA 50')]:f.add_trace(go.Scatter(x=d.ts,y=d[col],name=name,mode='lines',line=dict(width=1.3)))
if vwap:f.add_trace(go.Scatter(x=d.ts,y=d.vwap,name='VWAP',mode='lines',line=dict(width=2,dash='dot')))
f.update_layout(height=680,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=15,b=10),hovermode='x unified')
f.update_xaxes(showgrid=False);f.update_yaxes(side='right',gridcolor='#171717')
st.plotly_chart(f,use_container_width=True,config={'displaylogo':False,'scrollZoom':True})

if rsi_on:
    r=go.Figure(go.Scatter(x=d.ts,y=d.rsi,name='RSI 14',mode='lines'));r.add_hline(y=70,line_dash='dot');r.add_hline(y=30,line_dash='dot');r.update_layout(height=180,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',margin=dict(l=10,r=10,t=5,b=5),yaxis=dict(range=[0,100],side='right'));st.plotly_chart(r,use_container_width=True,config={'displaylogo':False})

st.markdown('<div class="panel"><div class="section">DATA STATUS</div><div class="muted">Historical candles are read from SQLite first. New data is requested from Upstox and upserted into SQLite during refresh. This screen is the SQLite-backed staging version before the existing production chart is switched over.</div></div>',unsafe_allow_html=True)
