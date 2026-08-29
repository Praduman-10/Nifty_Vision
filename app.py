import os
from datetime import date,timedelta
import numpy as np,pandas as pd,requests,plotly.graph_objects as go,streamlit as st
from streamlit_autorefresh import st_autorefresh
st.set_page_config(page_title='Nifty Vision',page_icon='◈',layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN',''));KEY='NSE_INDEX|Nifty 50'
FRAMES={'1 min':('minutes',1),'3 min':('minutes',3),'5 min':('minutes',5),'15 min':('minutes',15),'30 min':('minutes',30),'1 hour':('hours',1)}
st.markdown('''<style>.stApp{background:#050505;color:#f5f5f5}.block-container{max-width:1800px;padding-top:2.5rem!important}[data-testid="stSidebar"]{background:#090909;border-right:1px solid #252525}.k{font-size:.65rem;font-weight:800;letter-spacing:2px;color:#777}.title{font-size:2.5rem;font-weight:950;letter-spacing:-2px}.sub{color:#707070;font-size:.75rem}.card{background:#0d0d0d;border:1px solid #292929;border-radius:14px;padding:14px}.lab{font-size:.6rem;color:#777;font-weight:800;letter-spacing:1px}.val{font-size:1.3rem;font-weight:900;margin-top:5px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:#0b0b0b;border:1px solid #252525;border-radius:15px;padding:16px}.pt{font-size:.72rem;font-weight:900;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px}.read{font-size:.76rem;color:#999;line-height:1.55}.status{display:inline-block;border:1px solid #303030;border-radius:999px;padding:5px 10px;font-size:.62rem;font-weight:800;letter-spacing:.7px;color:#aaa}</style>''',unsafe_allow_html=True)
def headers():return {'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}
def parse_candles(rows):
 d=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','oi']);d['ts']=pd.to_datetime(d['ts'],utc=True).dt.tz_convert('Asia/Kolkata')
 for c in ['open','high','low','close','volume','oi']:d[c]=pd.to_numeric(d[c],errors='coerce')
 return d.sort_values('ts').drop_duplicates('ts').reset_index(drop=True)
@st.cache_data(ttl=20,show_spinner=False)
def candles(unit,interval):
 r=requests.get(f'https://api.upstox.com/v3/historical-candle/intraday/{KEY}/{unit}/{interval}',headers=headers(),timeout=20);r.raise_for_status();rows=r.json().get('data',{}).get('candles',[])
 if rows:return parse_candles(rows),'LIVE INTRADAY'
 to=date.today();back=28 if unit=='minutes' and interval<=15 else 80;fr=to-timedelta(days=back);r=requests.get(f'https://api.upstox.com/v3/historical-candle/{KEY}/{unit}/{interval}/{to:%Y-%m-%d}/{fr:%Y-%m-%d}',headers=headers(),timeout=20);r.raise_for_status();rows=r.json().get('data',{}).get('candles',[])
 if not rows:raise RuntimeError('Upstox returned no candles.');return parse_candles(rows),'LATEST HISTORICAL SESSION'
def add_indicators(d):
 d=d.copy();d['ema9']=d.close.ewm(span=9,adjust=False).mean();d['ema20']=d.close.ewm(span=20,adjust=False).mean();d['ema50']=d.close.ewm(span=50,adjust=False).mean();d['session']=d.ts.dt.date;tp=(d.high+d.low+d.close)/3;vol=pd.to_numeric(d.volume,errors='coerce').fillna(0);pv=tp*vol;cv=pv.groupby(d.session).cumsum();vv=vol.groupby(d.session).cumsum();
 if float(vol.sum())>0:d['vwap']=cv.div(vv.replace(0,np.nan));d['vwap_mode']='VWAP'
 else:d['vwap']=tp.groupby(d.session).expanding().mean().reset_index(level=0,drop=True).sort_index();d['vwap_mode']='VWAP PRICE PROXY'
 delta=d.close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();d['rsi']=100-100/(1+gain/loss.replace(0,np.nan));return d
PATTERN_MEANINGS={'DOJI':'Indecision; buyers and sellers are balanced.','HAMMER':'Bullish rejection of lower prices.','SHOOTING STAR':'Bearish rejection of higher prices.','BULLISH ENGULFING':'Strong bullish reversal signal.','BEARISH ENGULFING':'Strong bearish reversal signal.','PIERCING':'Bullish reversal after a decline.','DARK CLOUD':'Bearish reversal after an advance.','BULLISH HARAMI':'Potential bullish reversal / slowing selling.','BEARISH HARAMI':'Potential bearish reversal / slowing buying.'}
def detect_patterns(d):
 out=[]
 for i in range(1,len(d)):
  b,c=d.iloc[i-1],d.iloc[i];body=abs(c.close-c.open);rng=max(c.high-c.low,1e-9);lower=min(c.open,c.close)-c.low;upper=c.high-max(c.open,c.close)
  names=[]
  if body/rng<.15:names.append('DOJI')
  if lower>=max(body*2,1e-9) and upper<=max(body*.8,1e-9):names.append('HAMMER')
  if upper>=max(body*2,1e-9) and lower<=max(body*.8,1e-9):names.append('SHOOTING STAR')
  if b.close<b.open and c.close>c.open and c.open<=b.close and c.close>=b.open:names.append('BULLISH ENGULFING')
  if b.close>b.open and c.close<c.open and c.open>=b.close and c.close<=b.open:names.append('BEARISH ENGULFING')
  if b.close<b.open and c.close>c.open and c.open<b.close and c.close>(b.open+b.close)/2 and c.close<b.open:names.append('PIERCING')
  if b.close>b.open and c.close<c.open and c.open>b.close and c.close<(b.open+b.close)/2 and c.close>b.open:names.append('DARK CLOUD')
  if b.close<b.open and c.close>c.open and c.open>b.close and c.close<b.open:names.append('BULLISH HARAMI')
  if b.close>b.open and c.close<c.open and c.open<b.close and c.close>b.open:names.append('BEARISH HARAMI')
  for n in names:out.append({'i':i,'name':n,'meaning':PATTERN_MEANINGS[n]})
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
  ps=detect_patterns(d)
  for p in ps:
   row=d.iloc[p['i']];y=row.high if p['name'] in ['SHOOTING STAR','DOJI','BEARISH ENGULFING','DARK CLOUD','BEARISH HARAMI'] else row.low
   f.add_annotation(x=row.ts,y=y,text=p['name'],showarrow=True,arrowhead=2,ay=-28 if y==row.high else 28,font=dict(size=9))
 f.update_layout(height=650,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10),hovermode='x unified');f.update_xaxes(showgrid=False);f.update_yaxes(side='right',gridcolor='#171717');return f
st_autorefresh(interval=30000,key='nv_refresh');st.sidebar.markdown('**NIFTY VISION**\n\nLIVE MARKET INTELLIGENCE')
if not TOKEN:st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
frame=st.sidebar.selectbox('TIMEFRAME',list(FRAMES),index=2);unit,interval=FRAMES[frame];n=st.sidebar.slider('CANDLES',50,500,180,10);ema=st.sidebar.checkbox('EMA 9 / 20 / 50',True);vwap=st.sidebar.checkbox('VWAP',True);sr=st.sidebar.checkbox('Support / Resistance',True);show_patterns=st.sidebar.checkbox('Candle Patterns',True)
try:raw,mode=candles(unit,interval);d=add_indicators(raw.tail(n))
except Exception as e:st.error(f'Upstox feed failed: {type(e).__name__}: {e}');st.stop()
if len(d)<2:st.error('Not enough candles returned.');st.stop()
ps=detect_patterns(d);last,prev=d.iloc[-1],d.iloc[-2];chg=last.close-prev.close;pct=chg/prev.close*100;s,r=levels(d);bias='BULLISH' if last.close>last.ema20 and last.ema9>last.ema20 and last.close>last.vwap else ('BEARISH' if last.close<last.ema20 and last.ema9<last.ema20 and last.close<last.vwap else 'MIXED');bc='green' if bias=='BULLISH' else ('red' if bias=='BEARISH' else 'amber')
st.markdown("<div class='k'>NIFTY 50 • LIVE PRICE ACTION</div><div class='title'>Nifty Vision</div>",unsafe_allow_html=True);st.markdown(f"<div class='sub'>Upstox • {frame} candles • {last.ts.strftime('%d %b %Y %H:%M:%S %Z')} &nbsp; <span class='status'>{mode}</span> <span class='status'>{d.vwap_mode.iloc[-1]}</span></div>",unsafe_allow_html=True);st.divider();cols=st.columns(5);items=[('NIFTY',f'{last.close:,.2f}',f'{chg:+.2f} ({pct:+.2f}%)'),('BIAS',bias,'EMA + VWAP composite'),('RSI 14',f'{last.rsi:.1f}','Momentum'),('SUPPORT',f'{s:,.0f}','Recent range low'),('RESISTANCE',f'{r:,.0f}','Recent range high')]
for c,(a,b,x) in zip(cols,items):c.markdown(f"<div class='card'><div class='lab'>{a}</div><div class='val {bc if a=='BIAS' else ''}'>{b}</div><div class='sub'>{x}</div></div>",unsafe_allow_html=True)
left,right=st.columns([3.8,1.2],gap='large')
with left:
 st.markdown("<div class='pt'>PRICE ACTION MAP</div>",unsafe_allow_html=True);st.plotly_chart(chart(d,ema,vwap,sr,show_patterns),use_container_width=True,config={'displaylogo':False,'scrollZoom':True});vol=go.Figure(go.Bar(x=d.ts,y=d.volume));vol.update_layout(height=140,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',margin=dict(l=10,r=10,t=0,b=0));st.plotly_chart(vol,use_container_width=True,config={'displaylogo':False})
with right:
 st.markdown("<div class='panel'><div class='pt'>LIVE READ</div>",unsafe_allow_html=True);st.markdown(f"<div class='val {bc}'>{bias}</div><div class='read'>{'Price above VWAP with EMA alignment.' if bias=='BULLISH' else 'Price below VWAP with EMA alignment.' if bias=='BEARISH' else 'Signals are mixed; wait for confirmation.'}</div><br><div class='pt'>PATTERNS</div>",unsafe_allow_html=True)
 if ps:
  for p in ps[-8:]:st.markdown(f"<div class='read'><b>{p['name']}</b><br>{p['meaning']}</div><br>",unsafe_allow_html=True)
 else:st.markdown('<div class="read">No recognised candle patterns in the visible chart.</div>',unsafe_allow_html=True)
 rv=float(last.rsi);state='Overbought' if rv>=70 else 'Oversold' if rv<=30 else 'Neutral';st.markdown(f"<br><div class='pt'>MOMENTUM</div><div class='read'>RSI <b>{rv:.1f}</b> — {state}.<br>EMA9 is {'above' if last.ema9>last.ema20 else 'below'} EMA20.<br>Close is {'above' if last.close>last.vwap else 'below'} VWAP.</div></div>",unsafe_allow_html=True)
st.caption('Decision-support prototype only; rule-based signals are not investment advice.')