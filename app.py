import os
from datetime import date,timedelta
import numpy as np,pandas as pd,plotly.graph_objects as go,streamlit as st
from streamlit_autorefresh import st_autorefresh
from app_sqlite_patch import load_for_dashboard
st.set_page_config(page_title='Nifty Vision',page_icon='◈',layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN',''))
FRAMES=['1 min','3 min','5 min','15 min','30 min','1 hour','1 day']
st.markdown('''<style>.stApp{background:#050505;color:#f5f5f5}.block-container{max-width:1800px;padding-top:2.5rem!important}[data-testid="stSidebar"]{background:#090909;border-right:1px solid #252525}.k{font-size:.65rem;font-weight:800;letter-spacing:2px;color:#777}.title{font-size:2.5rem;font-weight:950;letter-spacing:-2px}.sub{color:#707070;font-size:.75rem}.card{background:#0d0d0d;border:1px solid #292929;border-radius:14px;padding:14px}.lab{font-size:.6rem;color:#777;font-weight:800;letter-spacing:1px}.val{font-size:1.3rem;font-weight:900;margin-top:5px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:#0b0b0b;border:1px solid #252525;border-radius:15px;padding:16px}.pt{font-size:.72rem;font-weight:900;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:10px}.read{font-size:.76rem;color:#999;line-height:1.55}.status{display:inline-block;border:1px solid #303030;border-radius:999px;padding:5px 10px;font-size:.62rem;font-weight:800;letter-spacing:.7px;color:#aaa}</style>''',unsafe_allow_html=True)
def indicators(d):
 d=d.copy();d['ema9']=d.close.ewm(span=9,adjust=False).mean();d['ema20']=d.close.ewm(span=20,adjust=False).mean();d['ema50']=d.close.ewm(span=50,adjust=False).mean();d['session']=d.ts.dt.date;tp=(d.high+d.low+d.close)/3;vol=pd.to_numeric(d.volume,errors='coerce').fillna(0);vv=vol.groupby(d.session).cumsum();d['vwap']=(tp*vol).groupby(d.session).cumsum().div(vv.replace(0,np.nan));delta=d.close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean();d['rsi']=100-100/(1+gain/loss.replace(0,np.nan));return d
def patterns(d):
 out=[]
 for i in range(1,len(d)):
  b,c=d.iloc[i-1],d.iloc[i];body=abs(c.close-c.open);rng=max(c.high-c.low,1e-9);lo=min(c.open,c.close)-c.low;up=c.high-max(c.open,c.close)
  if body/rng<.15:out.append((i,'DOJI','neutral','Indecision'))
  if lo>=max(body*2,1e-9) and up<=max(body*.8,1e-9):out.append((i,'HAMMER','bullish','Bullish lower-price rejection'))
  if up>=max(body*2,1e-9) and lo<=max(body*.8,1e-9):out.append((i,'SHOOTING STAR','bearish','Bearish higher-price rejection'))
  if b.close<b.open and c.close>c.open and c.open<=b.close and c.close>=b.open:out.append((i,'BULLISH ENGULFING','bullish','Strong bullish reversal'))
  if b.close>b.open and c.close<c.open and c.open>=b.close and c.close<=b.open:out.append((i,'BEARISH ENGULFING','bearish','Strong bearish reversal'))
 return out
def zones(d):
 x=d.tail(min(120,len(d)));price=float(x.close.iloc[-1]);atr=float((x.high-x.low).rolling(14).mean().iloc[-1]);atr=max(atr,price*.001);w=max(3,min(7,len(x)//20));lo=x.low.rolling(w,center=True).min();hi=x.high.rolling(w,center=True).max();s=x.loc[x.low.eq(lo),'low'].dropna();r=x.loc[x.high.eq(hi),'high'].dropna();sv=float(s[s<=price].max()) if not s[s<=price].empty else float(x.low.min());rv=float(r[r>=price].min()) if not r[r>=price].empty else float(x.high.max());h=atr*.35;return (sv-h,sv+h),(rv-h,rv+h)
def make_chart(d,ps):
 f=go.Figure(go.Candlestick(x=d.ts,open=d.open,high=d.high,low=d.low,close=d.close,name='NIFTY',increasing_line_color='#00e676',decreasing_line_color='#ff5252'))
 for c,n in [('ema9','EMA 9'),('ema20','EMA 20'),('ema50','EMA 50')]:f.add_trace(go.Scatter(x=d.ts,y=d[c],name=n,mode='lines'))
 f.add_trace(go.Scatter(x=d.ts,y=d.vwap,name='VWAP',mode='lines',line=dict(width=2,dash='dot')));(s1,s2),(r1,r2)=zones(d);f.add_hrect(y0=s1,y1=s2,fillcolor='rgba(0,230,118,.12)',line_color='#00e676',annotation_text='SUPPORT');f.add_hrect(y0=r1,y1=r2,fillcolor='rgba(255,82,82,.12)',line_color='#ff5252',annotation_text='RESISTANCE')
 for i,n,dr,meaning in {p[1]:p for p in ps}.values():
  row=d.iloc[i];col='#00e676' if dr=='bullish' else '#ff5252' if dr=='bearish' else '#ffc107';f.add_annotation(x=row.ts,y=row.low if dr=='bullish' else row.high,text=n,showarrow=True,arrowhead=2,ay=30 if dr=='bullish' else -30,font=dict(color=col,size=10),arrowcolor=col,bgcolor='rgba(5,5,5,.85)',bordercolor=col,borderwidth=1)
 f.update_layout(height=650,template='plotly_dark',paper_bgcolor='#080808',plot_bgcolor='#080808',xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10),hovermode='x unified');f.update_yaxes(side='right');return f
st_autorefresh(interval=30000,key='nv_refresh');st.sidebar.markdown('**NIFTY VISION**')
if not TOKEN:st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
frame=st.sidebar.selectbox('TIMEFRAME',FRAMES,index=2);n=st.sidebar.slider('CANDLES',50,1000,300,10);ema=st.sidebar.checkbox('EMA 9 / 20 / 50',True);vwap=st.sidebar.checkbox('VWAP',True);show=st.sidebar.checkbox('Candle Patterns',True)
try:raw,source=load_for_dashboard(frame,n);d=indicators(raw.tail(n))
except Exception as e:st.error(f'Market data failed: {type(e).__name__}: {e}');st.stop()
if len(d)<2:st.info('No stored candles yet. Run the historical backfill.');st.stop()
ps=patterns(d) if show else [];last,prev=d.iloc[-1],d.iloc[-2];chg=last.close-prev.close;pct=chg/prev.close*100;bias='BULLISH' if last.close>last.ema20 and last.ema9>last.ema20 and last.close>last.vwap else 'BEARISH' if last.close<last.ema20 and last.ema9<last.ema20 and last.close<last.vwap else 'MIXED';bc='green' if bias=='BULLISH' else 'red' if bias=='BEARISH' else 'amber';(s1,s2),(r1,r2)=zones(d)
st.markdown("<div class='k'>NIFTY 50 • PRICE ACTION</div><div class='title'>Nifty Vision</div>",unsafe_allow_html=True);st.markdown(f"<div class='sub'>{frame} • {last.ts.strftime('%d %b %Y %H:%M:%S %Z')} • <span class='status'>{source}</span></div>",unsafe_allow_html=True);st.divider();cols=st.columns(5)
for c,(a,b,x) in zip(cols,[('NIFTY',f'{last.close:,.2f}',f'{chg:+.2f} ({pct:+.2f}%)'),('BIAS',bias,'EMA + VWAP'),('RSI 14',f'{last.rsi:.1f}','Momentum'),('SUPPORT',f'{s1:,.0f}–{s2:,.0f}','Dynamic zone'),('RESISTANCE',f'{r1:,.0f}–{r2:,.0f}','Dynamic zone')]):c.markdown(f"<div class='card'><div class='lab'>{a}</div><div class='val {bc if a=='BIAS' else ''}'>{b}</div><div class='sub'>{x}</div></div>",unsafe_allow_html=True)
left,right=st.columns([3.8,1.2],gap='large')
with left:st.plotly_chart(make_chart(d,ps),use_container_width=True,config={'displaylogo':False,'scrollZoom':True})
with right:
 st.markdown("<div class='panel'><div class='pt'>LIVE READ</div>",unsafe_allow_html=True);st.markdown(f"<div class='val {bc}'>{bias}</div><div class='read'>Price is {'above' if last.close>last.vwap else 'below'} VWAP. EMA9 is {'above' if last.ema9>last.ema20 else 'below'} EMA20.</div><br><div class='pt'>PATTERNS</div>",unsafe_allow_html=True)
 latest={p[1]:p for p in ps}
 for i,nm,dr,meaning in latest.values():
  cls='green' if dr=='bullish' else 'red' if dr=='bearish' else 'amber';st.markdown(f"<div class='read'><b class='{cls}'>{nm}</b><br>{meaning}</div><br>",unsafe_allow_html=True)
 if not latest:st.markdown('<div class="read">No recognised patterns on screen.</div>',unsafe_allow_html=True)
 st.markdown('</div>',unsafe_allow_html=True)
