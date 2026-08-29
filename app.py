import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from app_sqlite_patch import load_for_dashboard
from market_intelligence import market_structure,signal_score
from pattern_engine import detect_patterns
from structure_engine import detect_structure
st.set_page_config(page_title='Nifty Vision',page_icon='◈',layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN','')); FRAMES=['1 min','3 min','5 min','15 min','30 min','1 hour','1 day']
st.markdown('''<style>
html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#050607!important;color:#f5f7fa!important} [data-testid="stToolbar"]{background:#050607!important} .stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}
[data-testid="stSidebar"]{background:#080a0c!important;border-right:1px solid #20252b}[data-testid="stSidebar"] *{color:#e7eaee!important}
.stSelectbox>div>div,.stRadio>div,.stSlider>div{background:#0b0e11!important;color:#fff!important}.stSelectbox label,.stRadio label,.stSlider label{color:#b7bec6!important}
.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.7rem;font-weight:950;letter-spacing:-2.5px;line-height:1;margin:.35rem 0 .5rem}.sub{color:#727b86;font-size:.72rem}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:15px 16px;min-height:92px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.35rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.card-note{font-size:.62rem;color:#69727c;margin-top:4px}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:17px;margin-bottom:12px}.panel-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1d2328;padding-bottom:11px;margin-bottom:13px}.pt{font-size:.76rem;font-weight:1000;letter-spacing:1.8px;text-transform:uppercase;color:#fff}.pill{border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;color:#aeb6bf}.divider{height:1px;background:#20252a;margin:18px 0}.read{font-size:.72rem;color:#999;line-height:1.5}.structure-card{border-radius:16px;padding:18px;border:1px solid #00e676;border-left:4px solid #00e676;background:#091b12;box-shadow:0 0 30px rgba(0,230,118,.10);margin-bottom:12px}.structure-card.bear{border-color:#ff5252;border-left-color:#ff5252;background:#1b0b0b;box-shadow:0 0 30px rgba(255,82,82,.10)}.structure-card.neutral{border-color:#ffc107;border-left-color:#ffc107;background:#171307}.structure-title{font-size:.6rem;font-weight:900;letter-spacing:1.8px;color:#9aa3ad}.structure-main{font-size:1.7rem;font-weight:950;margin:7px 0 2px}.structure-event{font-size:.75rem;color:#e2e6ea}.structure-conf{font-size:.67rem;color:#8b949e;margin-top:5px}.pattern-card{padding:10px 11px;border:1px solid #20262c;border-radius:10px;background:#0a0c0e;margin-bottom:8px}.pattern-card.bull{border-left:3px solid #00e676}.pattern-card.bear{border-left:3px solid #ff5252}.pattern-card.neutral{border-left:3px solid #ffc107}.pattern-name{font-size:.72rem;font-weight:900}.pattern-meta{font-size:.58rem;color:#77818b;margin-top:3px}.pattern-meaning{font-size:.67rem;color:#aab2ba;margin-top:5px;line-height:1.4}
</style>''',unsafe_allow_html=True)
def indicators(d,frame):
 d=d.copy();d['ema9']=d.close.ewm(span=9,adjust=False,min_periods=1).mean();d['ema20']=d.close.ewm(span=20,adjust=False,min_periods=1).mean();d['ema50']=d.close.ewm(span=50,adjust=False,min_periods=1).mean();d['session']=d.ts.dt.date;tp=(d.high+d.low+d.close)/3;vol=pd.to_numeric(d.volume,errors='coerce').fillna(0)
 if frame=='1 day':cv=vol.cumsum();d['vwap']=(tp*vol).cumsum().div(cv.replace(0,np.nan))
 else:vv=vol.groupby(d.session).cumsum();d['vwap']=(tp*vol).groupby(d.session).cumsum().div(vv.replace(0,np.nan))
 delta=d.close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean();rs=gain.div(loss.replace(0,np.nan));d['rsi']=100-100/(1+rs);d.loc[(loss==0)&(gain>0),'rsi']=100;return d
def zones(d):
 x=d.tail(min(120,len(d)));price=float(x.close.iloc[-1]);atr=float((x.high-x.low).rolling(14,min_periods=1).mean().iloc[-1]);atr=atr if np.isfinite(atr) and atr>0 else price*.001;w=max(3,min(7,max(1,len(x)//20)));lo=x.low.rolling(w,center=True,min_periods=1).min();hi=x.high.rolling(w,center=True,min_periods=1).max();s=x.loc[x.low.eq(lo),'low'];r=x.loc[x.high.eq(hi),'high'];below=s[s<=price];above=r[r>=price];sv=float(below.max()) if len(below) else float(x.low.min());rv=float(above.min()) if len(above) else float(x.high.max());
 if rv<=price:rv=float(x.high.max())
 if sv>=price:sv=float(x.low.min())
 h=atr*.35;return(sv-h,sv+h),(rv-h,rv+h)
def make_chart(d,ps,events,frame,show_ema,show_vwap,show_sr,show_structure):
 f=go.Figure(go.Candlestick(x=d.ts,open=d.open,high=d.high,low=d.low,close=d.close,name='NIFTY',increasing_line_color='#00e676',decreasing_line_color='#ff5252'))
 if show_ema:
  for c,n in [('ema9','EMA 9'),('ema20','EMA 20'),('ema50','EMA 50')]:f.add_trace(go.Scatter(x=d.ts,y=d[c],name=n,mode='lines',line=dict(width=1.7)))
 if show_vwap:f.add_trace(go.Scatter(x=d.ts,y=d.vwap,name='VWAP',mode='lines',line=dict(width=2,dash='dot')))
 (s1,s2),(r1,r2)=zones(d)
 if show_sr:f.add_hrect(y0=s1,y1=s2,fillcolor='rgba(0,230,118,.10)',line_color='#00e676',annotation_text='SUPPORT');f.add_hrect(y0=r1,y1=r2,fillcolor='rgba(255,82,82,.10)',line_color='#ff5252',annotation_text='RESISTANCE')
 if show_structure:
  for e in events:
   idx=e['index'];
   if idx not in d.index:continue
   row=d.loc[idx];typ=e['type'];bull=typ in ('HH','HL','BOS UP');col='#00e676' if bull else '#ff5252';y=float(row.high if typ in ('HH','LH','BOS UP','BOS DOWN') else row.low);f.add_annotation(x=row.ts,y=y,text=typ,showarrow=True,arrowhead=2,ay=-25 if bull else 25,font=dict(color=col,size=9),arrowcolor=col,bgcolor='rgba(5,5,5,.92)',bordercolor=col,borderwidth=1)
 for p in ps:
  row=d.iloc[p['index']];dr=p['direction'];col='#00e676' if dr=='bullish' else '#ff5252' if dr=='bearish' else '#ffc107';f.add_annotation(x=row.ts,y=row.low if dr=='bullish' else row.high,text=p['name'],showarrow=True,arrowhead=2,ay=30 if dr=='bullish' else -30,font=dict(color=col,size=9),arrowcolor=col,bgcolor='rgba(5,5,5,.92)',bordercolor=col,borderwidth=1)
 buttons=[dict(count=1,label='1M',step='month',stepmode='backward'),dict(count=3,label='3M',step='month',stepmode='backward'),dict(count=6,label='6M',step='month',stepmode='backward'),dict(count=1,label='1Y',step='year',stepmode='backward'),dict(step='all',label='ALL')] if frame=='1 day' else [dict(count=1,label='1D',step='day',stepmode='backward'),dict(count=5,label='5D',step='day',stepmode='backward'),dict(count=1,label='1M',step='month',stepmode='backward'),dict(step='all',label='ALL')]
 f.update_layout(height=650,template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',xaxis_rangeslider_visible=True,xaxis_rangeslider_thickness=.065,xaxis=dict(rangeselector=dict(buttons=buttons,bgcolor='#101316',activecolor='#242a30',font=dict(color='#d5dbe0',size=10))),margin=dict(l=8,r=8,t=25,b=8),hovermode='x unified',legend=dict(orientation='h',y=1.02,x=0,font=dict(size=10)));f.update_yaxes(side='right',gridcolor='#20262b');f.update_xaxes(gridcolor='#20262b');return f
st_autorefresh(interval=30000,key='nv_refresh');st.sidebar.markdown('### NIFTY VISION')
if not TOKEN:st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
frame=st.sidebar.radio('TIMEFRAME',FRAMES,index=2);n=st.sidebar.select_slider('CANDLES',options=[10,50,100,150,200,300,400,500,600,700,1000],value=300);st.sidebar.caption(f'1,000 candles loaded • showing {n:,}');show_ema=st.sidebar.checkbox('EMA 9 / 20 / 50',True);show_vwap=st.sidebar.checkbox('VWAP',True);show_sr=st.sidebar.checkbox('Support / Resistance',True);show_structure=st.sidebar.checkbox('Market Structure',True);show=st.sidebar.checkbox('Candle Patterns',True)
try:raw,source=load_for_dashboard(frame,1000);d=indicators(raw.tail(n),frame)
except Exception as e:st.error(f'Market data failed: {type(e).__name__}: {e}');st.stop()
if len(d)<2:st.info('No stored candles yet. Run the historical backfill.');st.stop()
ps=detect_patterns(d) if show else [];d,base=market_structure(d);struct=detect_structure(d);score=signal_score(base,ps);last,prev=d.iloc[-1],d.iloc[-2];chg=last.close-prev.close;pct=chg/prev.close*100;bias=struct['trend'];bc='green' if bias=='BULLISH' else 'red' if bias=='BEARISH' else 'amber';(s1,s2),(r1,r2)=zones(d)
st.markdown('<div class="kicker">NIFTY 50 • PRICE ACTION TERMINAL</div><div class="title">Nifty Vision</div>',unsafe_allow_html=True);st.markdown(f'<div class="sub">{frame} • {last.ts.strftime("%d %b %Y %H:%M:%S %Z")} • <span class="status">{source}</span> • <span class="status">LIVE • 30s</span></div>',unsafe_allow_html=True);st.markdown('<div class="divider"></div>',unsafe_allow_html=True)
cols=st.columns(7)
for c,(a,b,x) in zip(cols,[('NIFTY',f'{last.close:,.2f}',f'{chg:+.2f} ({pct:+.2f}%)'),('REGIME',bias,'Market structure'),('SETUP',struct['latest'],'Structure event'),('SIGNAL',f'{score:+d} / 5','Pattern + trend'),('RSI 14',f'{last.rsi:.1f}' if np.isfinite(last.rsi) else '—','Momentum'),('SUPPORT',f'{s1:,.0f}–{s2:,.0f}','Dynamic zone'),('RESISTANCE',f'{r1:,.0f}–{r2:,.0f}','Dynamic zone')]):c.markdown(f'<div class="card"><div class="lab">{a}</div><div class="val {bc if a in ("REGIME","SIGNAL") else ""}">{b}</div><div class="card-note">{x}</div></div>',unsafe_allow_html=True)
left,right=st.columns([3.75,1.25],gap='large')
with left:st.markdown('<div class="panel"><div class="panel-head"><div class="pt">PRICE ACTION</div><div class="pill">SCROLL • ZOOM • DRAG</div></div>',unsafe_allow_html=True);st.plotly_chart(make_chart(d,ps,struct['events'],frame,show_ema,show_vwap,show_sr,show_structure),use_container_width=True,config={'displaylogo':False,'scrollZoom':True,'doubleClick':'reset'});st.markdown('</div>',unsafe_allow_html=True)
with right:
 card_cls='structure-card' if bias=='BULLISH' else 'structure-card bear' if bias=='BEARISH' else 'structure-card neutral';main_cls=bc;st.markdown(f'<div class="{card_cls}"><div class="structure-title">MARKET STRUCTURE</div><div class="structure-main {main_cls}">{struct["trend"]}</div><div class="structure-event">Latest: <b>{struct["latest"]}</b></div><div class="structure-conf">Confidence: <b>{struct["confidence"]}</b></div></div>',unsafe_allow_html=True)
 st.markdown('<div class="panel"><div class="panel-head"><div class="pt">PATTERNS</div><div class="pill">LATEST</div></div>',unsafe_allow_html=True)
 for p in ps:
  cls='bull' if p['direction']=='bullish' else 'bear' if p['direction']=='bearish' else 'neutral';txt='BULLISH' if p['direction']=='bullish' else 'BEARISH' if p['direction']=='bearish' else 'NEUTRAL';color='green' if cls=='bull' else 'red' if cls=='bear' else 'amber';st.markdown(f'<div class="pattern-card {cls}"><div class="pattern-name {color}">{p["name"]}</div><div class="pattern-meta">{txt} • {p["confidence"]} confidence • {p["score"]}/3 confirmation</div><div class="pattern-meaning">{p["meaning"]}</div></div>',unsafe_allow_html=True)
 if not ps:st.markdown('<div class="read">No recognised patterns on screen.</div>',unsafe_allow_html=True)
 st.markdown('</div>',unsafe_allow_html=True)
