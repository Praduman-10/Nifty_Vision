import os
from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from order_book_stream import get_stream

st.set_page_config(page_title='Nifty Vision • D30 Order Book', page_icon='◈', layout='wide')
TOKEN = st.secrets.get('UPSTOX_ACCESS_TOKEN', os.getenv('UPSTOX_ACCESS_TOKEN', ''))
UNDERLYING = 'NSE_INDEX|Nifty 50'
EXPIRIES = ['current_week', 'next_week', 'far_week', 'current_month', 'next_month']

st.markdown('''<style>
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px;line-height:1.05}.sub{font-size:.68rem;color:#89929b}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.read{font-size:.68rem;color:#89929b;line-height:1.5}.signal{border-radius:16px;padding:18px;border:1px solid #30363d;background:#0b0e11;margin-bottom:14px}.signal.bull{border-color:#00e676;background:#091b12}.signal.bear{border-color:#ff5252;background:#1b0b0b}.signal-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px;color:#9aa3ad}.signal-main{font-size:1.65rem;font-weight:950;margin:7px 0 3px}.metric{background:#0a0d10;border:1px solid #20262c;border-radius:11px;padding:12px;margin-bottom:8px}.metric .name{font-size:.58rem;font-weight:900;letter-spacing:1.2px;color:#77818b}.metric .big{font-size:1.12rem;font-weight:950;margin-top:4px}.metric .desc{font-size:.6rem;color:#8d969f;margin-top:3px}
</style>''', unsafe_allow_html=True)

def api_get(path, params):
    r=requests.get('https://api.upstox.com/v2'+path,params=params,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20)
    try: body=r.json()
    except Exception: body={}
    if r.status_code>=400: raise RuntimeError(f'HTTP {r.status_code}: {body.get("errors") or body.get("message") or r.text[:300]}')
    if body.get('status')!='success': raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data',[])

def rows_from(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for k in ('data','items','results'):
            if isinstance(data.get(k),list): return data[k]
    return []

def resolve_expiry(kind):
    contracts=rows_from(api_get('/option/contract',{'instrument_key':UNDERLYING}))
    dates=sorted({str(x.get('expiry')) for x in contracts if isinstance(x,dict) and x.get('expiry') and str(x.get('expiry'))>=date.today().isoformat()})
    if not dates: raise RuntimeError('No future NIFTY option expiries were returned by Upstox.')
    if kind=='current_week': return dates[0]
    if kind=='next_week': return dates[min(1,len(dates)-1)]
    if kind=='far_week': return dates[min(2,len(dates)-1)]
    if kind=='current_month': return [d for d in dates if d[:7]==dates[0][:7]][-1]
    months=sorted({d[:7] for d in dates if d[:7]>dates[0][:7]})
    return [d for d in dates if d[:7]==months[0]][-1] if months else dates[-1]

def load_chain(kind):
    actual=resolve_expiry(kind)
    rows=rows_from(api_get('/option/chain',{'instrument_key':UNDERLYING,'expiry_date':actual}))
    if not rows: raise RuntimeError(f'No NIFTY option-chain data returned for {actual}.')
    return rows,actual

def option_rows(rows,side):
    out=[]
    for row in rows:
        if not isinstance(row,dict) or row.get('strike_price') is None: continue
        leg=row.get('call_options' if side=='CALL' else 'put_options') or {}
        md=leg.get('market_data') or {}
        out.append({'strike':float(row['strike_price']),'instrument_key':leg.get('instrument_key'),'ltp':md.get('ltp')})
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)

def extract_levels(snapshot):
    feed=snapshot.get('feed') or {}; full=feed.get('fullFeed') or {}; market=full.get('marketFF') or full.get('marketFf') or {}; level=market.get('marketLevel') or {}; quotes=level.get('bidAskQuote') or []
    rows=[]
    for i,q in enumerate(quotes[:30],1):
        if isinstance(q,dict): rows.append({'LEVEL':i,'BID QTY':float(q.get('bidQ') or 0),'BID PRICE':pd.to_numeric(q.get('bidP'),errors='coerce'),'ASK PRICE':pd.to_numeric(q.get('askP'),errors='coerce'),'ASK QTY':float(q.get('askQ') or 0)})
    df=pd.DataFrame(rows)
    ltp=pd.to_numeric((feed.get('ltpc') or {}).get('ltp'),errors='coerce')
    return df,{'ltp':float(ltp) if pd.notna(ltp) else np.nan,'oi':pd.to_numeric(market.get('oi'),errors='coerce'),'volume':pd.to_numeric(market.get('vtt'),errors='coerce')}

def analyse(d,meta):
    b=pd.to_numeric(d['BID QTY'],errors='coerce').fillna(0); a=pd.to_numeric(d['ASK QTY'],errors='coerce').fillna(0); tb=float(b.sum()); ta=float(a.sum()); total=tb+ta; imb=(tb-ta)/total if total else np.nan
    bb=float(d['BID PRICE'].dropna().iloc[0]) if d['BID PRICE'].notna().any() else np.nan; ba=float(d['ASK PRICE'].dropna().iloc[0]) if d['ASK PRICE'].notna().any() else np.nan; spread=ba-bb if np.isfinite(bb) and np.isfinite(ba) else np.nan; mid=(bb+ba)/2 if np.isfinite(bb) and np.isfinite(ba) else meta['ltp']; micro=((ba*b.iloc[0])+(bb*a.iloc[0]))/(b.iloc[0]+a.iloc[0]) if len(d) and np.isfinite(bb) and np.isfinite(ba) and b.iloc[0]+a.iloc[0] else mid
    bi=int(b.idxmax()); ai=int(a.idxmax()); bw=float(d.loc[bi,'BID PRICE']) if pd.notna(d.loc[bi,'BID PRICE']) else np.nan; aw=float(d.loc[ai,'ASK PRICE']) if pd.notna(d.loc[ai,'ASK PRICE']) else np.nan
    pressure='BUY-SIDE PRESSURE' if imb>=.15 else 'SELL-SIDE PRESSURE' if imb<=-.15 else 'BALANCED'; cls='bull' if pressure.startswith('BUY') else 'bear' if pressure.startswith('SELL') else ''; return locals()

st_autorefresh(interval=10000,key='d30_refresh')
st.markdown('<div class="kicker">NIFTY 50 • MICROSTRUCTURE</div><div class="title">D30 Order Book Analysis</div><div class="sub">30-level live market depth • both buy and sell sides • liquidity walls • imbalance • execution pressure</div>',unsafe_allow_html=True)
st.markdown('<span class="status">UPSTOX FULL D30 • WEBSOCKET</span> <span class="status">UI REFRESH 10s</span>',unsafe_allow_html=True)
st.divider()
if not TOKEN: st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.'); st.stop()

c1,c2,c3=st.columns([1.15,1.0,2.1])
with c1: expiry_kind=st.selectbox('EXPIRY',EXPIRIES,index=0)
with c2: side=st.radio('OPTION',['CALL','PUT'],horizontal=True)
with c3: st.caption('The selected contract streams Upstox full_d30 depth. The page refreshes every 10 seconds.')
try: chain,actual_expiry=load_chain(expiry_kind); options=option_rows(chain,side)
except Exception as exc: st.error(f'Option chain failed: {type(exc).__name__}: {exc}'); st.stop()
if options.empty: st.warning('No option contracts returned for this expiry/side.'); st.stop()
spot_values=pd.to_numeric(pd.Series([x.get('underlying_spot_price') for x in chain if isinstance(x,dict)]),errors='coerce').dropna(); spot=float(spot_values.iloc[0]) if len(spot_values) else np.nan
atm=float(options.loc[(options['strike']-spot).abs().idxmin(),'strike']) if np.isfinite(spot) else float(options.iloc[len(options)//2]['strike']); choices=options['strike'].tolist(); default=choices.index(atm) if atm in choices else len(choices)//2
strike=st.selectbox('STRIKE PRICE',choices,index=default,format_func=lambda x:f'{x:,.0f}'); selected=options.loc[options['strike']==strike].iloc[0]; instrument_key=selected['instrument_key']
if not instrument_key: st.error('Upstox did not return an instrument key for the selected option.'); st.stop()

stream=get_stream(TOKEN); stream.start(instrument_key); snapshot=stream.get(); stream_status=stream.status(); depth,meta=extract_levels(snapshot)
if depth.empty:
    st.info('Connecting to Upstox D30 depth… wait for the first live snapshot. If D30 is not enabled on the Upstox account, the stream will report an error.')
    if stream_status.get('error'): st.warning(f'D30 stream: {stream_status["error"]}')
    st.stop()

m=analyse(depth,meta); now=pd.Timestamp.now(tz=ZoneInfo('Europe/London')); cols=st.columns(7)
summary=[('LTP',meta['ltp'],'Last traded price',''),('BEST BID',m['bb'],'Level 1 bid','green'),('BEST ASK',m['ba'],'Level 1 ask','red'),('SPREAD',m['spread'],'Ask − bid','amber'),('D30 IMBALANCE',m['imb']*100,'30-level bid vs ask qty','green' if m['imb']>.05 else 'red' if m['imb']<-.05 else 'amber'),('MICROPRICE',m['micro'],'Level-1 depth pressure','green' if m['micro']>m['mid'] else 'red' if m['micro']<m['mid'] else 'amber'),('OI',meta['oi'],'Open interest','')]
for c,(name,value,note,cls) in zip(cols,summary):
    text='—' if pd.isna(value) else f'{float(value):,.2f}' if name!='OI' and name!='D30 IMBALANCE' else ('—' if pd.isna(value) else f'{float(value):,.0f}' if name=='OI' else f'{float(value):+.1f}%')
    c.markdown(f'<div class="card"><div class="lab">{name}</div><div class="val {cls}">{text}</div><div class="sub">{note}</div></div>',unsafe_allow_html=True)

signal_color='green' if m['cls']=='bull' else 'red' if m['cls']=='bear' else 'amber'
st.markdown(f'<div class="signal {m["cls"]}"><div class="signal-title">ORDER BOOK READ • {side} {strike:,.0f} • {actual_expiry}</div><div class="signal-main {signal_color}">{m["pressure"]}</div><div class="read">30-level displayed liquidity is {m["imb"]*100:+.1f}% imbalanced. Largest bid wall: <b>{m["bw"]:,.2f}</b>. Largest ask wall: <b>{m["aw"]:,.2f}</b>. Snapshot refreshed {now.strftime("%H:%M:%S %Z")}.</div></div>',unsafe_allow_html=True)

left,right=st.columns([3.4,1.6],gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">30-LEVEL MARKET DEPTH • BUY + SELL</div></div>',unsafe_allow_html=True)
    display=depth.copy(); st.dataframe(display,use_container_width=True,hide_index=True,height=760); st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="section"><div class="pt">D30 DEPTH PROFILE</div></div>',unsafe_allow_html=True)
    fig=go.Figure(); fig.add_trace(go.Bar(x=depth['BID PRICE'],y=depth['BID QTY'],name='BIDS')); fig.add_trace(go.Bar(x=depth['ASK PRICE'],y=depth['ASK QTY'],name='ASKS')); fig.update_layout(height=420,template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',barmode='group',margin=dict(l=10,r=10,t=10,b=10),legend=dict(orientation='h')); st.plotly_chart(fig,use_container_width=True); st.markdown('</div>',unsafe_allow_html=True)
with right:
    st.markdown('<div class="panel"><div class="section"><div class="pt">D30 ORDER FLOW</div></div>',unsafe_allow_html=True)
    metrics=[('TOTAL BID QTY',m['tb'],'All 30 displayed bid levels'),('TOTAL ASK QTY',m['ta'],'All 30 displayed ask levels'),('BID WALL',m['bw'],'Largest bid quantity level'),('ASK WALL',m['aw'],'Largest ask quantity level'),('TOP BID QTY',depth.iloc[0]['BID QTY'],'Level 1 bid'),('TOP ASK QTY',depth.iloc[0]['ASK QTY'],'Level 1 ask'),('MID → MICRO',f'{m["mid"]:,.2f} → {m["micro"]:,.2f}','Depth pressure direction')]
    for name,value,desc in metrics:
        text=value if isinstance(value,str) else ('—' if pd.isna(value) else f'{float(value):,.0f}' if name not in ('BID WALL','ASK WALL') else f'{float(value):,.2f}')
        st.markdown(f'<div class="metric"><div class="name">{name}</div><div class="big">{text}</div><div class="desc">{desc}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="section"><div class="pt">READ THIS CORRECTLY</div></div><div class="read">D30 shows the displayed top 30 buy and sell levels supplied by Upstox. Imbalance and liquidity walls describe the current order-book snapshot; they are not guaranteed price predictions. Orders can be cancelled or executed quickly.</div></div>',unsafe_allow_html=True)
