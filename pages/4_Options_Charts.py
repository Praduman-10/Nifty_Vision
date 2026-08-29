import os
from datetime import date
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title='Nifty Vision • Option Charts', page_icon='◈', layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN','')); UNDERLYING='NSE_INDEX|Nifty 50'; EXPIRIES=['current_week','next_week','current_month','next_month']
st.markdown('''<style>html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#050607!important;color:#f5f7fa!important}.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c!important;border-right:1px solid #20252b}[data-testid="stSidebar"] *{color:#e7eaee!important}.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px}.sub{font-size:.68rem;color:#89929b}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase;border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:86px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.28rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.note{font-size:.62rem;color:#707982;margin-top:4px}.badge{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}</style>''',unsafe_allow_html=True)
def api(path,params):
 r=requests.get('https://api.upstox.com/v2'+path,params=params,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20)
 try:b=r.json()
 except Exception:b={}
 if r.status_code>=400:raise RuntimeError(f'HTTP {r.status_code}: {b.get("errors") or b.get("message") or r.text[:250]}')
 if b.get('status')!='success':raise RuntimeError(b.get('errors') or b.get('message') or 'Upstox API error')
 return b.get('data',[])
def rows(x):
 if isinstance(x,list):return x
 if isinstance(x,dict):
  for k in ('data','items','results'):
   if isinstance(x.get(k),list):return x[k]
 return []
def expiry(k):
 rs=rows(api('/option/contract',{'instrument_key':UNDERLYING}));ds=sorted({str(x.get('expiry')) for x in rs if isinstance(x,dict) and x.get('expiry') and str(x['expiry'])>=date.today().isoformat()})
 if not ds:raise RuntimeError('No future NIFTY expiries returned by Upstox.')
 if k=='current_week':return ds[0]
 if k=='next_week':return ds[min(1,len(ds)-1)]
 if k=='current_month':return [d for d in ds if d[:7]==ds[0][:7]][-1]
 if k=='next_month':
  m=sorted({d[:7] for d in ds if d[:7]>ds[0][:7]});return [d for d in ds if d[:7]==m[0]][-1] if m else ds[-1]
 return k
def chain(k):
 rs=rows(api('/option/chain',{'instrument_key':UNDERLYING,'expiry_date':k}))
 if not rs:k=expiry(k);rs=rows(api('/option/chain',{'instrument_key':UNDERLYING,'expiry_date':k}))
 if not rs:raise RuntimeError(f'No option chain returned for {k}.')
 out=[]
 for x in rs:
  if not isinstance(x,dict) or x.get('strike_price') is None:continue
  c=x.get('call_options') or {};p=x.get('put_options') or {};cm=c.get('market_data') or {};pm=p.get('market_data') or {};cg=c.get('option_greeks') or {};pg=p.get('option_greeks') or {}
  out.append({'strike':float(x['strike_price']),'spot':pd.to_numeric(x.get('underlying_spot_price'),errors='coerce'),'CE LTP':pd.to_numeric(cm.get('ltp'),errors='coerce'),'PE LTP':pd.to_numeric(pm.get('ltp'),errors='coerce'),'CE OI':pd.to_numeric(cm.get('oi'),errors='coerce'),'PE OI':pd.to_numeric(pm.get('oi'),errors='coerce'),'CE IV':pd.to_numeric(cg.get('iv'),errors='coerce'),'PE IV':pd.to_numeric(pg.get('iv'),errors='coerce'),'CE Delta':pd.to_numeric(cg.get('delta'),errors='coerce'),'PE Delta':pd.to_numeric(pg.get('delta'),errors='coerce'),'CE Gamma':pd.to_numeric(cg.get('gamma'),errors='coerce'),'PE Gamma':pd.to_numeric(pg.get('gamma'),errors='coerce'),'CE Theta':pd.to_numeric(cg.get('theta'),errors='coerce'),'PE Theta':pd.to_numeric(pg.get('theta'),errors='coerce'),'CE Vega':pd.to_numeric(cg.get('vega'),errors='coerce'),'PE Vega':pd.to_numeric(pg.get('vega'),errors='coerce')})
 if not out:raise RuntimeError('No valid strikes in Upstox response.')
 return pd.DataFrame(out).sort_values('strike').reset_index(drop=True),k
st_autorefresh(interval=30000,key='option_chart_refresh')
st.markdown('<div class="kicker">NIFTY 50 • DERIVATIVES</div><div class="title">Option Charts</div><div class="sub">Strike-wise option indicators • CE / PE price • OI • IV • Greeks</div>',unsafe_allow_html=True);st.divider()
if not TOKEN:st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
c1,c2,c3=st.columns([1.1,1.2,2.7])
with c1:ek=st.selectbox('EXPIRY',EXPIRIES)
with c2:metric=st.selectbox('INDICATOR',['Option Price','Open Interest','Implied Volatility','Delta','Gamma','Theta','Vega'])
with c3:window=st.select_slider('STRIKES AROUND ATM',[5,7,10,15,20],10)
try:df,actual=chain(ek)
except Exception as e:st.error(f'Option chart failed: {type(e).__name__}: {e}');st.stop()
spot=float(df.spot.dropna().iloc[0]);atm_i=int((df.strike-spot).abs().idxmin());lo=max(0,atm_i-window);hi=min(len(df),atm_i+window+1);v=df.iloc[lo:hi].copy();atm=float(df.loc[atm_i,'strike'])
st.markdown(f'<span class="badge">EXPIRY {actual}</span> <span class="badge">SPOT {spot:,.2f}</span> <span class="badge">ATM {atm:,.0f}</span>',unsafe_allow_html=True)
cols=st.columns(5);summary=[('NIFTY',f'{spot:,.2f}','Spot',''),('ATM',f'{atm:,.0f}','Nearest strike',''),('CE ATM',f'{df.loc[atm_i,"CE LTP"]:,.2f}' if pd.notna(df.loc[atm_i,'CE LTP']) else '—','ATM call','green'),('PE ATM',f'{df.loc[atm_i,"PE LTP"]:,.2f}' if pd.notna(df.loc[atm_i,'PE LTP']) else '—','ATM put','red'),('ATM IV',f'{np.nanmean([df.loc[atm_i,"CE IV"],df.loc[atm_i,"PE IV"]]):.2f}','Average CE/PE IV','amber')]
for c,(a,b,n,cl) in zip(cols,summary):c.markdown(f'<div class="card"><div class="lab">{a}</div><div class="val {cl}">{b}</div><div class="note">{n}</div></div>',unsafe_allow_html=True)
st.markdown('<div class="panel"><div class="pt">OPTION INDICATOR CHART</div>',unsafe_allow_html=True);fig=go.Figure()
if metric=='Option Price':fig.add_trace(go.Scatter(x=v.strike,y=v['CE LTP'],mode='lines+markers',name='CALL PREMIUM'));fig.add_trace(go.Scatter(x=v.strike,y=v['PE LTP'],mode='lines+markers',name='PUT PREMIUM'))
elif metric=='Open Interest':fig.add_trace(go.Bar(x=v.strike,y=v['CE OI'],name='CALL OI'));fig.add_trace(go.Bar(x=v.strike,y=-v['PE OI'],name='PUT OI'))
elif metric=='Implied Volatility':fig.add_trace(go.Scatter(x=v.strike,y=v['CE IV'],mode='lines+markers',name='CALL IV'));fig.add_trace(go.Scatter(x=v.strike,y=v['PE IV'],mode='lines+markers',name='PUT IV'))
else:fig.add_trace(go.Scatter(x=v.strike,y=v[f'CE {metric}'],mode='lines+markers',name=f'CALL {metric.upper()}'));fig.add_trace(go.Scatter(x=v.strike,y=v[f'PE {metric}'],mode='lines+markers',name=f'PUT {metric.upper()}'))
fig.add_vline(x=spot,line_dash='dash',annotation_text=f'SPOT {spot:,.0f}');fig.add_vline(x=atm,line_dash='dot',annotation_text='ATM');fig.update_layout(height=520,template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',hovermode='x unified',margin=dict(l=10,r=10,t=15,b=10),legend=dict(orientation='h',y=1.03,x=0));fig.update_xaxes(title='Strike',gridcolor='#20262b');fig.update_yaxes(gridcolor='#20262b');st.plotly_chart(fig,use_container_width=True,config={'displaylogo':False,'scrollZoom':True,'doubleClick':'reset'});st.markdown('</div>',unsafe_allow_html=True)
st.markdown('<div class="panel"><div class="pt">STRIKE INDICATOR TABLE</div>',unsafe_allow_html=True);show_cols=['strike','CE LTP','PE LTP','CE OI','PE OI','CE IV','PE IV','CE Delta','PE Delta','CE Gamma','PE Gamma'];st.dataframe(v[show_cols],use_container_width=True,hide_index=True,height=360);st.markdown('</div>',unsafe_allow_html=True)
