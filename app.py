import os
from datetime import date, timedelta
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title='Nifty Vision',page_icon='◈',layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN',''));KEY='NSE_INDEX|Nifty 50'
FRAMES={'1 min':('minutes',1),'3 min':('minutes',3),'5 min':('minutes',5),'15 min':('minutes',15),'30 min':('minutes',30),'1 hour':('hours',1)}
st.markdown('''<style>.stApp{background:#050505;color:#f5f5f5}.block-container{max-width:1800px;padding-top:2.5rem!important}[data-testid="stSidebar"]{background:#090909;border-right:1px solid #252525}.k{font-size:.65rem;font-weight:800;letter-spacing:2px;color:#777}.title{font-size:2.5rem;font-weight:950;letter-spacing:-2px}.sub{color:#707070;font-size:.75rem}.card{background:#0d0d0d;border:1px solid #292929;border-radius:14px;padding:14px}.lab{font-size:.6rem;color:#777;font-weight:800;letter-spacing:1px}.val{font-size:1.3rem;font-weight:900;margin-top:5px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:#0b0b0b;border:1px solid #252525;border-radius:15px;padding:16px}.pt{font-size:.72rem;font-weight:900;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px}.read{font-size:.76rem;color:#999;line-height:1.55}.status{display:inline-block;border:1px solid #303030;border-radius:999px;padding:5px 10px;font-size:.62rem;font-weight:800;letter-spacing:.7px;color:#aaa}</style>''',unsafe_allow_html=True)

def headers():return {'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}
def parse_candles(rows):
 d=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','oi']);d['ts']=pd.to_datetime(d.ts,utc=True).dt.tz_convert('Asia/Kolkata')
 for c in ['open','high','low','close','volume','oi']:d[c]=pd.to_numeric(d[c],errors='coerce')
 return d.sort_values('ts').drop_duplicates('ts').reset_index(drop=True)
@st.cache_data(ttl=20,show_spinner=False)
def candles(unit,interval):
 u=f'https://api.upstox.com/v3/historical-candle/intraday/{KEY}/{unit}/{interval}';r=requests.get(u,headers=headers(),timeout=20);r.raise_for_status();rows=r.json().get('data',{}).get('candles',[])
 if rows:return parse_candles(rows),'LIVE INTRADAY'
 to=date.today();back=28 if unit=='minutes' and interval<=15 else 80;fr=to-timedelta(days=back);u=f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{to:%Y-%m-%d}/{fr:%Y-%m-%d}';h=requests.get(u,headers=headers(),timeout=20);h.raise_for_status();rows=h.json().get('data',{}).get('candles',[])
 if not rows:raise RuntimeError('Upstox returned no candles.')
 return parse_candles(rows),'LATEST HISTORICAL SESSION'
def add_indicators(d):
 d=d.copy();d['ema9']=d.close.ewm(span=9,adjust=False).mean();d['ema20']=d.close.ewm(span=20,adjust=False).mean();d['ema50']=d.close.ewm(span=50,adjust=False).mean();d['session']=d.ts.dt.date;tp=(d.high+d.low+d.close)/3;vol=pd.to_numeric(d.volume,errors='coerce').fillna(0);pv=tp*vol;cp=pv.groupby(d.session).cumsum();cv=vol.groupby(d.session).cumsum();usable=float(vol.sum())>0
 d['vwap']=cp.div(cv.replace(0,np.nan)) if usable else tp.groupby(d.session).expanding().mean().reset_index(level=0,drop=True).sort_index();d['vwap_mode']='VWAP' if usable else 'VWAP PRICE PROXY';delta=d.close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();d['rsi']=100-100/(1+gain/loss.replace(0,np.nan));return d

def scan_patterns(d):
    out=[]
    for i in range(len(d)):
        c=d.iloc[i];o,h,l,cl=c.open,c.high,c.low,c.close;body=abs(cl-o);rng=max(h-l,1e-9);upper=h-max(o,cl);lower=min(o,cl)-l
        if body/rng<=.15:out.append((i,'DOJI','Indecision','amber'))
        if lower>=max(body*2,(rng*.35)) and upper<=max(body*.5,rng*.15):out.append((i,'HAMMER','Bullish rejection','green'))
        if upper>=max(body*2,(rng*.35)) and lower<=max(body*.5,rng*.15):out.append((i,'SHOOTING STAR','Bearish rejection','red'))
        if i>=1:
            p=d.iloc[i-1]
            if p.close<p.open and cl>o and o<=p.close and cl>=p.open:out.append((i,'BULL ENGULF','Bullish reversal','green'))
            if p.close>p.open and cl<o and o>=p.close and cl<=p.open:out.append((i,'BEAR ENGULF','Bearish reversal','red'))
            if p.close<p.open and cl>o and o<p.close and cl>(p.open+p.close)/2 and cl<p.open:out.append((i,'PIERCING','Bullish reversal','green'))
            if p.close>p.open and cl<o and o>p.close and cl<(p.open+p.close)/2 and cl>p.open:out.append((i,'DARK CLOUD','Bearish reversal','red'))
            if p.close<p.open and cl>o and o>p.close and cl<p.open:out.append((i,'BULL HARAMI','Potential reversal','green'))
            if p.close>p.open and cl<o and o<p.close and cl>p.open:out.append((i,'BEAR HARAMI','Potential reversal','red'))
    return out

def levels(d):x=d.tail(40);return float(x.low.min()),float(x.high.max())
def chart(d,ema,vwap,sr,show_patterns):
 f=go.Figure(go.Candlestick(x=d.ts,open=d.open,high=d.high,low=d.low,close=d.close,name='NIFTY',increasing_line_color='#00e676',decreasing_line_color='#ff5252'))
 if ema:
  for c,n in [('ema9','EMA 9'),('ema20','EMA 20'),('ema50','EMA 50')]:f.add_trace(go.Scatter(x=d.ts,y=d[c],name=n,mode='lines',line=dict(width=1.3)))
 if vwap:f.add_trace(go.Scatter(x=d.ts,y=d.vwap,name=d.vwap_mode.iloc[-1],mode='lines',line=dict(width=2.5,dash='dot')))
 if sr:
  s,r=levels(d);f.add_hline(y=s,line_dash='dot',annotation_text=f'Support {s:,.0f}');f.add_hline(y=r,line_dash='dot',annotation_text=f'Resistance {r:,.0f}')
 if show_patterns:
  for i,name,desc,kind in scan_patterns(d):
   c=d.iloc[i];f.add_annotation(x=c.ts,y=c.high+(d.high.max()-d.low.min())*.018,text=name,showarrow=False,bgcolor='rgba(0,0,0,.82)',bordercolor='#666',font=dict(size=9),yanchor='bottom')
 f.update_layout(height=650,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10),hovermode='x unified');f.update_xaxes(showgrid=False);f.update_yaxes(side='right',gridcolor='#171717');return f

st_autorefresh(interval=30000,key='nv_refresh');st.sidebar.markdown('**NIFTY VISION**\n\nLIVE MARKET INTELLIGENCE')
if not TOKEN:st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
frame=st.sidebar.selectbox('TIMEFRAME',list(FRAMES),index=2);unit,interval=FRAMES[frame];n=st.sidebar.slider('CANDLES',50,500,180,10);ema=st.sidebar.checkbox('EMA 9 / 20 / 50',True);vwap=st.sidebar.checkbox('VWAP',True);sr=st.sidebar.checkbox('Support / Resistance',True);show_patterns=st.sidebar.checkbox('CANDLE PATTERNS',True)
try:raw,mode=candles(unit,interval);d=add_indicators(raw.tail(n))
except Exception as e:st.error(f'Upstox feed failed: {type(e).__name__}: {e}');st.stop()
if len(d)<2:st.error('Not enough candles returned.');st.stop()
found=scan_patterns(d);last,prev=d.iloc[-1],d.iloc[-2];chg=last.close-prev.close;pct=chg/prev.close*100;s,r=levels(d);bias='BULLISH' if last.close>last.ema20 and last.ema9>last.ema20 and last.close>last.vwap else ('BEARISH' if last.close<last.ema20 and last.ema9<last.ema20 and last.close<last.vwap else 'MIXED');bc='green' if bias=='BULLISH' else ('red' if bias=='BEARISH' else 'amber')
st.markdown("<div class='k'>NIFTY 50 • LIVE PRICE ACTION</div><div class='title'>Nifty Vision</div>",unsafe_allow_html=True);st.markdown(f"<div class='sub'>Upstox • {frame} candles • {last.ts.strftime('%d %b %Y %H:%M:%S %Z')} &nbsp; <span class='status'>{mode}</span> <span class='status'>{d.vwap_mode.iloc[-1]}</span></div>",unsafe_allow_html=True);st.divider()
cols=st.columns(5);items=[('NIFTY',f'{last.close:,.2f}',f'{chg:+.2f} ({pct:+.2f}%)'),('BIAS',bias,'EMA + VWAP composite'),('RSI 14',f'{last.rsi:.1f}','Momentum'),('SUPPORT',f'{s:,.0f}','Recent range low'),('RESISTANCE',f'{r:,.0f}','Recent range high')]
for c,(a,b,x) in zip(cols,items):c.markdown(f"<div class='card'><div class='lab'>{a}</div><div class='val {bc if a=='BIAS' else ''}'>{b}</div><div class='sub'>{x}</div></div>",unsafe_allow_html=True)
left,right=st.columns([3.8,1.2],gap='large')
with left:
 st.markdown("<div class='pt'>PRICE ACTION MAP</div>",unsafe_allow_html=True);st.plotly_chart(chart(d,ema,vwap,sr,show_patterns),use_container_width=True,config={'displaylogo':False,'scrollZoom':True})
 vol=go.Figure(go.Bar(x=d.ts,y=d.volume));vol.update_layout(height=140,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',margin=dict(l=10,r=10,t=0,b=0));st.plotly_chart(vol,use_container_width=True,config={'displaylogo':False})
with right:
 st.markdown("<div class='panel'><div class='pt'>LIVE READ</div>",unsafe_allow_html=True);st.markdown(f"<div class='val {bc}'>{bias}</div><div class='read'>{'Price above VWAP with EMA alignment.' if bias=='BULLISH' else 'Price below VWAP with EMA alignment.' if bias=='BEARISH' else 'Signals are mixed; wait for confirmation.'}</div><br><div class='pt'>PATTERNS FOUND</div>",unsafe_allow_html=True)
 recent=found[-8:]
 if recent:
  for i,a,b,c in reversed(recent):st.markdown(f"<div class='read'><b class='{c}'>{a}</b> — {d.iloc[i].ts.strftime('%H:%M')}<br>{b}</div><br>",unsafe_allow_html=True)
 else:st.markdown('<div class="read">No patterns matched the current candle definitions.</div>',unsafe_allow_html=True)
 rv=float(last.rsi);state='Overbought' if rv>=70 else 'Oversold' if rv<=30 else 'Neutral';st.markdown(f"<div class='pt'>MOMENTUM</div><div class='read'>RSI <b>{rv:.1f}</b> — {state}.<br>EMA9 is {'above' if last.ema9>last.ema20 else 'below'} EMA20.<br>Close is {'above' if last.close>last.vwap else 'below'} VWAP.</div></div>",unsafe_allow_html=True)
st.caption('Decision-support prototype only; pattern markers are rule-based and are not investment advice.')