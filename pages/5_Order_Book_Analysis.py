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
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}
.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px;line-height:1.05}.sub{font-size:.68rem;color:#89929b}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.read{font-size:.68rem;color:#89929b;line-height:1.5}.signal{border-radius:16px;padding:18px;border:1px solid #30363d;background:#0b0e11;margin-bottom:14px}.signal.bull{border-color:#00e676;background:#091b12}.signal.bear{border-color:#ff5252;background:#1b0b0b}.signal-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px;color:#9aa3ad}.signal-main{font-size:1.65rem;font-weight:950;margin:7px 0 3px}.metric{background:#0a0d10;border:1px solid #20262c;border-radius:11px;padding:12px;margin-bottom:8px}.metric .name{font-size:.58rem;font-weight:900;letter-spacing:1.2px;color:#77818b}.metric .big{font-size:1.12rem;font-weight:950;margin-top:4px}.metric .desc{font-size:.6rem;color:#8d969f;margin-top:3px}
</style>''', unsafe_allow_html=True)


def api_get(path, params):
    r = requests.get('https://api.upstox.com/v2' + path, params=params, headers={
        'Accept': 'application/json', 'Authorization': f'Bearer {TOKEN}'
    }, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {body.get('errors') or body.get('message') or r.text[:300]}")
    if body.get('status') != 'success':
        raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data', [])


def rows_from(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('data', 'items', 'results'):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def resolve_expiry(kind):
    contracts = rows_from(api_get('/option/contract', {'instrument_key': UNDERLYING}))
    dates = sorted({str(x.get('expiry')) for x in contracts if isinstance(x, dict) and x.get('expiry') and str(x.get('expiry')) >= date.today().isoformat()})
    if not dates:
        raise RuntimeError('No future NIFTY option expiries were returned by Upstox.')
    if kind == 'current_week':
        return dates[0]
    if kind == 'next_week':
        return dates[min(1, len(dates) - 1)]
    if kind == 'far_week':
        return dates[min(2, len(dates) - 1)]
    if kind == 'current_month':
        return [d for d in dates if d[:7] == dates[0][:7]][-1]
    if kind == 'next_month':
        months = sorted({d[:7] for d in dates if d[:7] > dates[0][:7]})
        return [d for d in dates if d[:7] == months[0]][-1] if months else dates[-1]
    return kind


def load_chain(expiry_kind):
    actual = resolve_expiry(expiry_kind)
    rows = rows_from(api_get('/option/chain', {'instrument_key': UNDERLYING, 'expiry_date': actual}))
    if not rows:
        raise RuntimeError(f'No NIFTY option-chain data returned for {actual}.')
    return rows, actual


def option_rows(rows, side):
    out = []
    for row in rows:
        if not isinstance(row, dict) or row.get('strike_price') is None:
            continue
        leg = row.get('call_options' if side == 'CALL' else 'put_options') or {}
        md = leg.get('market_data') or {}
        out.append({
            'strike': float(row['strike_price']),
            'instrument_key': leg.get('instrument_key'),
            'ltp': md.get('ltp'),
        })
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)


def extract_levels(snapshot):
    feed = snapshot.get('feed') or {}
    full = feed.get('fullFeed') or {}
    market = full.get('marketFF') or full.get('marketFf') or {}
    level = market.get('marketLevel') or {}
    quotes = level.get('bidAskQuote') or []
    rows = []
    for i, q in enumerate(quotes[:30], start=1):
        if not isinstance(q, dict):
            continue
        rows.append({
            'LEVEL': i,
            'BID QTY': float(q.get('bidQ') or 0),
            'BID PRICE': pd.to_numeric(q.get('bidP'), errors='coerce'),
            'ASK PRICE': pd.to_numeric(q.get('askP'), errors='coerce'),
            'ASK QTY': float(q.get('askQ') or 0),
        })
    df = pd.DataFrame(rows)
    ltp = pd.to_numeric((feed.get('ltpc') or {}).get('ltp'), errors='coerce')
    meta = {
        'ltp': float(ltp) if pd.notna(ltp) else np.nan,
        'oi': pd.to_numeric(market.get('oi'), errors='coerce'),
        'volume': pd.to_numeric(market.get('vtt'), errors='coerce'),
        'total_bid': pd.to_numeric(market.get('tbq'), errors='coerce'),
        'total_ask': pd.to_numeric(market.get('tsq'), errors='coerce'),
    }
    return df, meta


def analyse(depth, meta):
    if depth.empty:
        return {}
    b = pd.to_numeric(depth['BID QTY'], errors='coerce').fillna(0)
    a = pd.to_numeric(depth['ASK QTY'], errors='coerce').fillna(0)
    total_b = float(b.sum())
    total_a = float(a.sum())
    total = total_b + total_a
    imbalance = (total_b - total_a) / total if total else np.nan
    best_bid = float(depth['BID PRICE'].dropna().iloc[0]) if depth['BID PRICE'].notna().any() else np.nan
    best_ask = float(depth['ASK PRICE'].dropna().iloc[0]) if depth['ASK PRICE'].notna().any() else np.nan
    spread = best_ask - best_bid if np.isfinite(best_bid) and np.isfinite(best_ask) else np.nan
    mid = (best_bid + best_ask) / 2 if np.isfinite(best_bid) and np.isfinite(best_ask) else meta['ltp']
    top_b = float(b.iloc[0]) if len(b) else 0
    top_a = float(a.iloc[0]) if len(a) else 0
    top_total = top_b + top_a
    top_imbalance = (top_b - top_a) / top_total if top_total else np.nan
    bid_wall_i = int(b.idxmax())
    ask_wall_i = int(a.idxmax())
    bid_wall_price = float(depth.loc[bid_wall_i, 'BID PRICE']) if pd.notna(depth.loc[bid_wall_i, 'BID PRICE']) else np.nan
    ask_wall_price = float(depth.loc[ask_wall_i, 'ASK PRICE']) if pd.notna(depth.loc[ask_wall_i, 'ASK PRICE']) else np.nan
    micro = ((best_ask * top_b) + (best_bid * top_a)) / top_total if top_total and np.isfinite(best_bid) and np.isfinite(best_ask) else mid
    pressure = 'BUY-SIDE PRESSURE' if imbalance >= .15 else 'SELL-SIDE PRESSURE' if imbalance <= -.15 else 'BALANCED'
    cls = 'bull' if pressure.startswith('BUY') else 'bear' if pressure.startswith('SELL') else ''
    return locals()


st_autorefresh(interval=1000, key='d30_refresh')
st.markdown('<div class="kicker">NIFTY 50 • MICROSTRUCTURE</div><div class="title">D30 Order Book Analysis</div><div class="sub">30-level live market depth • both buy and sell sides • liquidity walls • imbalance • execution pressure</div>', unsafe_allow_html=True)
st.markdown('<span class="status">UPSTOX FULL D30 • WEBSOCKET</span> <span class="status">UI REFRESH 1s</span>', unsafe_allow_html=True)
st.divider()

if not TOKEN:
    st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.')
    st.stop()

c1, c2, c3 = st.columns([1.15, 1.0, 2.1])
with c1:
    expiry_kind = st.selectbox('EXPIRY', EXPIRIES, index=0)
with c2:
    side = st.radio('OPTION', ['CALL', 'PUT'], horizontal=True)
with c3:
    st.caption('The selected option contract is streamed continuously through Upstox full_d30. Select any strike and both sides of its 30-level book are shown.')

try:
    chain, actual_expiry = load_chain(expiry_kind)
    options = option_rows(chain, side)
except Exception as exc:
    st.error(f'Option chain failed: {type(exc).__name__}: {exc}')
    st.stop()

if options.empty:
    st.warning('No option contracts returned for this expiry/side.')
    st.stop()

spot_values = pd.to_numeric(pd.Series([x.get('underlying_spot_price') for x in chain if isinstance(x, dict)]), errors='coerce').dropna()
spot = float(spot_values.iloc[0]) if len(spot_values) else np.nan
atm = float(options.loc[(options['strike'] - spot).abs().idxmin(), 'strike']) if np.isfinite(spot) else float(options.iloc[len(options) // 2]['strike'])
strike_choices = options['strike'].tolist()
default_idx = strike_choices.index(atm) if atm in strike_choices else len(strike_choices) // 2
strike = st.selectbox('STRIKE PRICE', strike_choices, index=default_idx, format_func=lambda x: f'{x:,.0f}')
selected = options.loc[options['strike'] == strike].iloc[0]
instrument_key = selected['instrument_key']
if not instrument_key:
    st.error('Upstox did not return an instrument key for the selected option.')
    st.stop()

stream = get_stream(TOKEN)
stream.start(instrument_key)
snapshot = stream.get()
status = stream.status()

depth, meta = extract_levels(snapshot)
if depth.empty:
    st.info('Connecting to Upstox D30 depth… The first full snapshot normally arrives immediately after the WebSocket subscription. Keep this page open for a moment.')
    if status.get('error'):
        st.warning(f'D30 stream: {status["error"]}')
    st.stop()

m = analyse(depth, meta)
now = pd.Timestamp.now(tz=ZoneInfo('Europe/London'))

cols = st.columns(7)
summary = [
    ('LTP', f'{m["meta"]["ltp"]:,.2f}' if np.isfinite(m['meta']['ltp']) else '—', 'Last traded price', ''),
    ('BEST BID', f'{m["best_bid"]:,.2f}' if np.isfinite(m['best_bid']) else '—', 'Level 1 bid', 'green'),
    ('BEST ASK', f'{m["best_ask"]:,.2f}' if np.isfinite(m['best_ask']) else '—', 'Level 1 ask', 'red'),
    ('SPREAD', f'{m["spread"]:,.2f}' if np.isfinite(m['spread']) else '—', 'Ask − bid', 'amber'),
    ('D30 IMBALANCE', f'{m["imbalance"]*100:+.1f}%' if np.isfinite(m['imbalance']) else '—', '30-level bid vs ask qty', 'green' if m['imbalance'] > .05 else 'red' if m['imbalance'] < -.05 else 'amber'),
    ('MICROPRICE', f'{m["micro"]:,.2f}' if np.isfinite(m['micro']) else '—', 'Level-1 depth pressure', 'green' if m['micro'] > m['mid'] else 'red' if m['micro'] < m['mid'] else 'amber'),
    ('OI', f'{float(m["meta"]["oi"]):,.0f}' if pd.notna(m['meta']['oi']) else '—', 'Open interest', ''),
]
for c, (name, value, note, cls) in zip(cols, summary):
    c.markdown(f'<div class="card"><div class="lab">{name}</div><div class="val {cls}">{value}</div><div class="sub">{note}</div></div>', unsafe_allow_html=True)

signal_color = 'green' if m['cls'] == 'bull' else 'red' if m['cls'] == 'bear' else 'amber'
st.markdown(f'<div class="signal {m["cls"]}"><div class="signal-title">ORDER BOOK READ • {side} {strike:,.0f} • {actual_expiry}</div><div class="signal-main {signal_color}">{m["pressure"]}</div><div class="read">30-level displayed liquidity is currently {m["imbalance"]*100:+.1f}% imbalanced toward the bid/ask side. Largest bid wall: <b>{m["bid_wall_price"]:,.2f}</b>. Largest ask wall: <b>{m["ask_wall_price"]:,.2f}</b>. Snapshot received via the live D30 WebSocket at {now.strftime("%H:%M:%S %Z")}.</div></div>', unsafe_allow_html=True)

left, right = st.columns([3.4, 1.6], gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">30-LEVEL MARKET DEPTH • BUY + SELL</div></div>', unsafe_allow_html=True)
    display = depth.copy()
    display['BID QTY'] = display['BID QTY'].map(lambda x: f'{x:,.0f}')
    display['BID PRICE'] = display['BID PRICE'].map(lambda x: f'{x:,.2f}' if pd.notna(x) else '—')
    display['ASK PRICE'] = display['ASK PRICE'].map(lambda x: f'{x:,.2f}' if pd.notna(x) else '—')
    display['ASK QTY'] = display['ASK QTY'].map(lambda x: f'{x:,.0f}')
    st.dataframe(display, use_container_width=True, hide_index=True, height=720)
    st.markdown('</div>', unsafe_allow_html=True)
with right:
    metrics = [
        ('30L BID QTY', f'{m["total_b"]:,.0f}', 'Displayed bid quantity across 30 levels'),
        ('30L ASK QTY', f'{m["total_a"]:,.0f}', 'Displayed ask quantity across 30 levels'),
        ('TOP-LEVEL IMBALANCE', f'{m["top_imbalance"]*100:+.1f}%' if np.isfinite(m['top_imbalance']) else '—', 'Level-1 bid vs ask pressure'),
        ('BID WALL', f'{m["bid_wall_price"]:,.2f}' if np.isfinite(m['bid_wall_price']) else '—', 'Largest displayed bid level'),
        ('ASK WALL', f'{m["ask_wall_price"]:,.2f}' if np.isfinite(m['ask_wall_price']) else '—', 'Largest displayed ask level'),
        ('TOTAL BUY QTY', f'{float(m["meta"]["total_bid"]):,.0f}' if pd.notna(m['meta']['total_bid']) else '—', 'Upstox total buy quantity'),
        ('TOTAL SELL QTY', f'{float(m["meta"]["total_ask"]):,.0f}' if pd.notna(m['meta']['total_ask']) else '—', 'Upstox total sell quantity'),
    ]
    for name, value, desc in metrics:
        st.markdown(f'<div class="metric"><div class="name">{name}</div><div class="big">{value}</div><div class="desc">{desc}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="section"><div class="pt">DEPTH PRESSURE MAP</div></div>', unsafe_allow_html=True)
chart = go.Figure()
chart.add_trace(go.Bar(y=depth['LEVEL'], x=-depth['BID QTY'], orientation='h', name='BUY DEPTH', hovertemplate='Level %{y}<br>Bid qty %{x:,.0f}<extra></extra>'))
chart.add_trace(go.Bar(y=depth['LEVEL'], x=depth['ASK QTY'], orientation='h', name='SELL DEPTH', hovertemplate='Level %{y}<br>Ask qty %{x:,.0f}<extra></extra>'))
chart.update_layout(height=760, barmode='relative', template='plotly_dark', paper_bgcolor='#080a0b', plot_bgcolor='#080a0b', margin=dict(l=10,r=10,t=10,b=10), xaxis_title='Displayed quantity', yaxis_title='Depth level', yaxis=dict(autorange='reversed'), legend=dict(orientation='h'))
st.plotly_chart(chart, use_container_width=True, config={'displaylogo': False})
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="read">Note: D30 is displayed exchange market depth, not hidden orders or guaranteed future support/resistance. Large orders can be cancelled or executed quickly. Upstox provides full_d30 through its WebSocket feed and requires the D30/Plus entitlement for this stream.</div>', unsafe_allow_html=True)
