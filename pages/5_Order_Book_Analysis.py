import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title='Nifty Vision • Order Book', page_icon='◈', layout='wide')
TOKEN = st.secrets.get('UPSTOX_ACCESS_TOKEN', os.getenv('UPSTOX_ACCESS_TOKEN', ''))
UNDERLYING = 'NSE_INDEX|Nifty 50'
EXPIRIES = ['current_week', 'next_week', 'far_week', 'current_month', 'next_month']

st.markdown('''<style>
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px;line-height:1.05}.sub{font-size:.68rem;color:#89929b}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.read{font-size:.68rem;color:#89929b;line-height:1.5}.signal{border-radius:16px;padding:18px;border:1px solid #30363d;background:#0b0e11;margin-bottom:14px}.signal.bull{border-color:#00e676;background:#091b12}.signal.bear{border-color:#ff5252;background:#1b0b0b}.signal-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px;color:#9aa3ad}.signal-main{font-size:1.65rem;font-weight:950;margin:7px 0 3px}.metric{background:#0a0d10;border:1px solid #20262c;border-radius:11px;padding:12px;margin-bottom:8px}.metric .name{font-size:.58rem;font-weight:900;letter-spacing:1.2px;color:#77818b}.metric .big{font-size:1.12rem;font-weight:950;margin-top:4px}.metric .desc{font-size:.6rem;color:#8d969f;margin-top:3px}
</style>''', unsafe_allow_html=True)

def api_get_v2(path, params):
    r = requests.get('https://api.upstox.com/v2' + path, params=params, headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}, timeout=20)
    try: body = r.json()
    except Exception: body = {}
    if r.status_code >= 400: raise RuntimeError(f'HTTP {r.status_code}: {body.get("errors") or body.get("message") or r.text[:300]}')
    if body.get('status') != 'success': raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data', [])

def api_get_v3(path, params):
    r = requests.get('https://api.upstox.com/v3' + path, params=params, headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}, timeout=20)
    try: body = r.json()
    except Exception: body = {}
    if r.status_code >= 400: raise RuntimeError(f'HTTP {r.status_code}: {body.get("errors") or body.get("message") or r.text[:300]}')
    if body.get('status') != 'success': raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data', {})

def rows_from(data):
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for k in ('data','items','results'):
            if isinstance(data.get(k), list): return data[k]
    return []

def resolve_expiry(kind):
    contracts = rows_from(api_get_v2('/option/contract', {'instrument_key':UNDERLYING}))
    dates = sorted({str(x.get('expiry')) for x in contracts if isinstance(x,dict) and x.get('expiry') and str(x.get('expiry')) >= date.today().isoformat()})
    if not dates: raise RuntimeError('No future NIFTY option expiries were returned by Upstox.')
    if kind == 'current_week': return dates[0]
    if kind == 'next_week': return dates[min(1,len(dates)-1)]
    if kind == 'far_week': return dates[min(2,len(dates)-1)]
    if kind == 'current_month': return [d for d in dates if d[:7] == dates[0][:7]][-1]
    months = sorted({d[:7] for d in dates if d[:7] > dates[0][:7]})
    return [d for d in dates if d[:7] == months[0]][-1] if months else dates[-1]

def load_chain(kind):
    actual = resolve_expiry(kind)
    rows = rows_from(api_get_v2('/option/chain', {'instrument_key':UNDERLYING, 'expiry_date':actual}))
    if not rows: raise RuntimeError(f'No NIFTY option-chain data returned for {actual}.')
    return rows, actual

def option_rows(rows, side):
    out=[]
    for row in rows:
        if not isinstance(row,dict) or row.get('strike_price') is None: continue
        leg = row.get('call_options' if side == 'CALL' else 'put_options') or {}
        md = leg.get('market_data') or {}
        out.append({'strike':float(row['strike_price']), 'instrument_key':leg.get('instrument_key'), 'ltp':md.get('ltp')})
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)

def extract_d5(quote):
    if not isinstance(quote, dict): return pd.DataFrame(), {}
    # V3 Full Market Quotes uses market_depth; keep fallbacks for common Upstox shapes.
    depth = quote.get('market_depth') or quote.get('marketDepth') or quote.get('depth') or {}
    bids = depth.get('buy') or depth.get('bids') or quote.get('bids') or []
    asks = depth.get('sell') or depth.get('asks') or quote.get('asks') or []
    if isinstance(bids, dict): bids = bids.get('bidAskQuote') or bids.get('quotes') or []
    if isinstance(asks, dict): asks = asks.get('bidAskQuote') or asks.get('quotes') or []
    rows=[]
    for i in range(5):
        b = bids[i] if i < len(bids) else {}
        a = asks[i] if i < len(asks) else {}
        def val(obj,*keys):
            for k in keys:
                if isinstance(obj,dict) and obj.get(k) is not None: return obj.get(k)
            return np.nan
        rows.append({'LEVEL':i+1,'BID QTY':pd.to_numeric(val(b,'quantity','bidQ','bq'),errors='coerce'),'BID PRICE':pd.to_numeric(val(b,'price','bidP','bp'),errors='coerce'),'ASK PRICE':pd.to_numeric(val(a,'price','askP','ap'),errors='coerce'),'ASK QTY':pd.to_numeric(val(a,'quantity','askQ','aq'),errors='coerce')})
    df=pd.DataFrame(rows)
    meta={'ltp':pd.to_numeric(quote.get('last_price',quote.get('ltp')),errors='coerce'),'oi':pd.to_numeric(quote.get('oi',quote.get('open_interest')),errors='coerce'),'volume':pd.to_numeric(quote.get('volume',quote.get('vtt')),errors='coerce')}
    return df,meta

def fetch_d5(instrument_key):
    data = api_get_v3('/market-quote/quotes', {'instrument_key':instrument_key})
    if not isinstance(data,dict) or not data: return pd.DataFrame(), {}
    quote = next(iter(data.values())) if all(isinstance(v,dict) for v in data.values()) else data
    return extract_d5(quote)

def analyse(d, meta):
    b=d['BID QTY'].fillna(0); a=d['ASK QTY'].fillna(0); tb=float(b.sum()); ta=float(a.sum()); total=tb+ta; imb=(tb-ta)/total if total else np.nan
    bb=float(d['BID PRICE'].dropna().iloc[0]) if d['BID PRICE'].notna().any() else np.nan; ba=float(d['ASK PRICE'].dropna().iloc[0]) if d['ASK PRICE'].notna().any() else np.nan
    spread=ba-bb if np.isfinite(bb) and np.isfinite(ba) else np.nan; mid=(bb+ba)/2 if np.isfinite(bb) and np.isfinite(ba) else meta['ltp']
    micro=((ba*b.iloc[0])+(bb*a.iloc[0]))/(b.iloc[0]+a.iloc[0]) if len(d) and np.isfinite(bb) and np.isfinite(ba) and b.iloc[0]+a.iloc[0] else mid
    bi=int(b.idxmax()); ai=int(a.idxmax()); bw=float(d.loc[bi,'BID PRICE']) if pd.notna(d.loc[bi,'BID PRICE']) else np.nan; aw=float(d.loc[ai,'ASK PRICE']) if pd.notna(d.loc[ai,'ASK PRICE']) else np.nan
    pressure='BUY-SIDE PRESSURE' if imb >= .15 else 'SELL-SIDE PRESSURE' if imb <= -.15 else 'BALANCED'; cls='bull' if pressure.startswith('BUY') else 'bear' if pressure.startswith('SELL') else ''
    return locals()

st_autorefresh(interval=10000, key='order_book_refresh')
st.markdown('<div class="kicker">NIFTY 50 • MICROSTRUCTURE</div><div class="title">Order Book Analysis</div><div class="sub">Live Upstox D5 market depth • top 5 buy and sell levels • liquidity walls • imbalance • execution pressure</div>', unsafe_allow_html=True)
st.markdown('<span class="status">UPSTOX D5 • LIVE</span> <span class="status">UI REFRESH 10s</span>', unsafe_allow_html=True)
st.divider()
if not TOKEN: st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.'); st.stop()

c1,c2,c3=st.columns([1.15,1.0,2.1])
with c1: expiry_kind=st.selectbox('EXPIRY',EXPIRIES,index=0)
with c2: side=st.radio('OPTION',['CALL','PUT'],horizontal=True)
with c3: st.caption('The selected contract uses Upstox standard market depth. No Upstox Plus / D30 entitlement is required.')
try:
    chain,actual_expiry=load_chain(expiry_kind); options=option_rows(chain,side)
except Exception as exc: st.error(f'Option chain failed: {type(exc).__name__}: {exc}'); st.stop()
if options.empty: st.warning('No option contracts returned for this expiry/side.'); st.stop()
spot_values=pd.to_numeric(pd.Series([x.get('underlying_spot_price') for x in chain if isinstance(x,dict)]),errors='coerce').dropna(); spot=float(spot_values.iloc[0]) if len(spot_values) else np.nan
atm=float(options.loc[(options['strike']-spot).abs().idxmin(),'strike']) if np.isfinite(spot) else float(options.iloc[len(options)//2]['strike']); choices=options['strike'].tolist(); default=choices.index(atm) if atm in choices else len(choices)//2
strike=st.selectbox('STRIKE PRICE',choices,index=default,format_func=lambda x:f'{x:,.0f}'); selected=options.loc[options['strike']==strike].iloc[0]; instrument_key=selected['instrument_key']
if not instrument_key: st.error('Upstox did not return an instrument key for the selected option.'); st.stop()

try: depth,meta=fetch_d5(instrument_key)
except Exception as exc: st.error(f'Market depth failed: {type(exc).__name__}: {exc}'); st.stop()
if depth.empty:
    st.warning('Upstox returned no market-depth levels for this contract yet. Try another strike or wait for the next 10-second refresh.'); st.stop()

m=analyse(depth,meta); cols=st.columns(7)
summary=[('LTP',meta['ltp'],'Last traded price',''),('BEST BID',m['bb'],'Level 1 bid','green'),('BEST ASK',m['ba'],'Level 1 ask','red'),('SPREAD',m['spread'],'Ask − bid','amber'),('D5 IMBALANCE',m['imb']*100,'5-level bid vs ask qty','green' if m['imb']>.05 else 'red' if m['imb']<-.05 else 'amber'),('MICROPRICE',m['micro'],'Level-1 depth pressure','green' if m['micro']>m['mid'] else 'red' if m['micro']<m['mid'] else 'amber'),('OI',meta['oi'],'Open interest','')]
for c,(name,value,note,cls) in zip(cols,summary):
    text='—' if pd.isna(value) else f'{float(value):,.2f}' if name not in ('OI','D5 IMBALANCE') else ('—' if pd.isna(value) else f'{float(value):,.0f}' if name=='OI' else f'{float(value):+.1f}%')
    c.markdown(f'<div class="card"><div class="lab">{name}</div><div class="val {cls}">{text}</div><div class="sub">{note}</div></div>',unsafe_allow_html=True)

signal_color='green' if m['cls']=='bull' else 'red' if m['cls']=='bear' else 'amber'
st.markdown(f'<div class="signal {m["cls"]}"><div class="signal-title">ORDER BOOK READ • {side} {strike:,.0f} • {actual_expiry}</div><div class="signal-main {signal_color}">{m["pressure"]}</div><div class="read">The visible top 5 levels are {m["imb"]*100:+.1f}% imbalanced. Largest bid wall: <b>{m["bw"]:,.2f}</b>. Largest ask wall: <b>{m["aw"]:,.2f}</b>. Data refreshes every 10 seconds.</div></div>',unsafe_allow_html=True)

left,right=st.columns([3.4,1.6],gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">5-LEVEL MARKET DEPTH • BUY + SELL</div></div>',unsafe_allow_html=True)
    st.dataframe(depth,use_container_width=True,hide_index=True,height=360)
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="section"><div class="pt">D5 DEPTH PROFILE</div></div>',unsafe_allow_html=True)
    fig=go.Figure(); fig.add_trace(go.Bar(x=depth['BID PRICE'],y=depth['BID QTY'],name='BIDS')); fig.add_trace(go.Bar(x=depth['ASK PRICE'],y=depth['ASK QTY'],name='ASKS')); fig.update_layout(height=420,template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',barmode='group',margin=dict(l=10,r=10,t=10,b=10),legend=dict(orientation='h')); st.plotly_chart(fig,use_container_width=True)
    st.markdown('</div>',unsafe_allow_html=True)
with right:
    st.markdown('<div class="panel"><div class="section"><div class="pt">ORDER FLOW METRICS</div></div>',unsafe_allow_html=True)
    metrics=[('TOTAL BID QTY',m['tb'],'All 5 displayed bid levels'),('TOTAL ASK QTY',m['ta'],'All 5 displayed ask levels'),('BID WALL',m['bw'],'Largest bid price level'),('ASK WALL',m['aw'],'Largest ask price level'),('TOP BID QTY',depth.iloc[0]['BID QTY'],'Level 1 bid'),('TOP ASK QTY',depth.iloc[0]['ASK QTY'],'Level 1 ask'),('MID → MICRO',f'{m["mid"]:,.2f} → {m["micro"]:,.2f}','Depth pressure direction')]
    for name,value,desc in metrics:
        text=value if isinstance(value,str) else ('—' if pd.isna(value) else f'{float(value):,.0f}' if name not in ('BID WALL','ASK WALL') else f'{float(value):,.2f}')
        st.markdown(f'<div class="metric"><div class="name">{name}</div><div class="big">{text}</div><div class="desc">{desc}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="section"><div class="pt">READ THIS CORRECTLY</div></div><div class="read">This page uses Upstox standard D5 market depth, showing the top five visible buy and sell levels. Imbalance, microprice and liquidity walls describe the current order-book snapshot; they are not guaranteed price predictions. Orders can be cancelled or executed quickly.</div></div>',unsafe_allow_html=True)
