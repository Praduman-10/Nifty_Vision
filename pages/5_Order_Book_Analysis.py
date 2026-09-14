# Nifty Vision • Order Book Analysis
import os
from datetime import datetime
from zoneinfo import ZoneInfo

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
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}
.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px;line-height:1.05}.sub{font-size:.68rem;color:#89929b}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.book-card{border-radius:16px;padding:18px;border:1px solid #30363d;background:#0b0e11;margin-bottom:14px}.book-card.bull{border-color:#00e676;background:#091b12}.book-card.bear{border-color:#ff5252;background:#1b0b0b}.book-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px;color:#9aa3ad}.book-main{font-size:1.65rem;font-weight:950;margin:7px 0 3px}.mini{font-size:.64rem;color:#9aa3ad;line-height:1.45}.metric{background:#0a0d10;border:1px solid #20262c;border-radius:11px;padding:12px;margin-bottom:8px}.metric .name{font-size:.58rem;font-weight:900;letter-spacing:1.2px;color:#77818b}.metric .big{font-size:1.12rem;font-weight:950;margin-top:4px}.metric .desc{font-size:.6rem;color:#8d969f;margin-top:3px}
</style>''', unsafe_allow_html=True)


def api_get_v2(path, params):
    r = requests.get('https://api.upstox.com/v2' + path, params=params,
                     headers={'Accept': 'application/json', 'Authorization': f'Bearer {TOKEN}'}, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {body.get('errors') or body.get('message') or r.text[:300]}")
    if body.get('status') != 'success':
        raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data', [])


def api_get_v3(path, params):
    r = requests.get('https://api.upstox.com/v3' + path, params=params,
                     headers={'Accept': 'application/json', 'Authorization': f'Bearer {TOKEN}'}, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {body.get('errors') or body.get('message') or r.text[:300]}")
    if body.get('status') != 'success':
        raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    return body.get('data', {})


def as_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('data', 'items', 'results'):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def load_chain(expiry):
    rows = as_rows(api_get_v2('/option/chain', {'instrument_key': UNDERLYING, 'expiry_date': expiry}))
    if not rows:
        raise RuntimeError(f'No NIFTY option-chain data returned for {expiry}.')
    return rows


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
            'bid_price': md.get('bid_price'),
            'bid_qty': md.get('bid_qty', 0),
            'ask_price': md.get('ask_price'),
            'ask_qty': md.get('ask_qty', 0),
            'oi': md.get('oi', 0),
            'volume': md.get('volume', 0),
            'iv': (leg.get('option_greeks') or {}).get('iv'),
            'delta': (leg.get('option_greeks') or {}).get('delta'),
        })
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)


def extract_quote(data, instrument_key):
    if not isinstance(data, dict):
        return {}
    # V3 quote keys may be represented as NSE_FO:NIFTY... while the request uses NSE_FO|token.
    for key, value in data.items():
        if isinstance(value, dict) and (value.get('instrument_token') == instrument_key or key.replace(':', '|') == instrument_key):
            return value
    if len(data) == 1:
        return next(iter(data.values()))
    return {}


def depth_rows(quote):
    depth = quote.get('depth') or {}
    buys = depth.get('buy') or []
    sells = depth.get('sell') or []
    bid = pd.DataFrame([{'side': 'BID', 'level': i + 1, 'price': x.get('price'), 'quantity': x.get('quantity', 0), 'orders': x.get('orders', 0)} for i, x in enumerate(buys)])
    ask = pd.DataFrame([{'side': 'ASK', 'level': i + 1, 'price': x.get('price'), 'quantity': x.get('quantity', 0), 'orders': x.get('orders', 0)} for i, x in enumerate(sells)])
    return bid, ask


def fmt(x, digits=2):
    try:
        return '—' if pd.isna(x) else f'{float(x):,.{digits}f}'
    except Exception:
        return '—'


def analysis(bid, ask, ltp):
    bq = pd.to_numeric(bid['quantity'], errors='coerce').fillna(0) if not bid.empty else pd.Series(dtype=float)
    aq = pd.to_numeric(ask['quantity'], errors='coerce').fillna(0) if not ask.empty else pd.Series(dtype=float)
    total_bid = float(bq.sum())
    total_ask = float(aq.sum())
    total = total_bid + total_ask
    imbalance = (total_bid - total_ask) / total if total else np.nan
    best_bid = float(bid.iloc[0]['price']) if not bid.empty else np.nan
    best_ask = float(ask.iloc[0]['price']) if not ask.empty else np.nan
    spread = best_ask - best_bid if np.isfinite(best_bid) and np.isfinite(best_ask) else np.nan
    mid = (best_bid + best_ask) / 2 if np.isfinite(best_bid) and np.isfinite(best_ask) else ltp
    # Microprice weights the mid toward the side with less displayed liquidity.
    micro = ((best_ask * total_bid) + (best_bid * total_ask)) / total if total and np.isfinite(best_bid) and np.isfinite(best_ask) else mid
    top_bid = float(bq.iloc[0]) if len(bq) else 0
    top_ask = float(aq.iloc[0]) if len(aq) else 0
    top_total = top_bid + top_ask
    top_imb = (top_bid - top_ask) / top_total if top_total else np.nan
    bid_wall = float(bid.loc[bq.idxmax(), 'price']) if len(bid) else np.nan
    ask_wall = float(ask.loc[aq.idxmax(), 'price']) if len(ask) else np.nan
    concentration_bid = top_bid / total_bid if total_bid else np.nan
    concentration_ask = top_ask / total_ask if total_ask else np.nan
    if imbalance >= 0.25:
        pressure, cls = 'BUY-SIDE PRESSURE', 'bull'
    elif imbalance <= -0.25:
        pressure, cls = 'SELL-SIDE PRESSURE', 'bear'
    else:
        pressure, cls = 'BALANCED', ''
    liquidity = 'HIGH' if total >= 5000 else 'MEDIUM' if total >= 1000 else 'LOW'
    return locals()


st_autorefresh(interval=10000, key='order_book_refresh')
st.markdown('<div class="kicker">NIFTY 50 • MICROSTRUCTURE</div><div class="title">Order Book Analysis</div><div class="sub">Live displayed liquidity • bid/ask imbalance • spread • liquidity walls • execution pressure</div>', unsafe_allow_html=True)
st.markdown('<div class="status">LIVE UPSTOX • 10s REFRESH</div>', unsafe_allow_html=True)
st.divider()

if not TOKEN:
    st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.')
    st.stop()

c1, c2, c3 = st.columns([1.15, 1.0, 1.35])
with c1:
    expiry = st.selectbox('EXPIRY', EXPIRIES, index=0)
with c2:
    side = st.radio('OPTION', ['CALL', 'PUT'], horizontal=True)
with c3:
    st.caption('Choose the expiry and option side, then select the strike. The book refreshes every 10 seconds.')

try:
    chain = load_chain(expiry)
    options = option_rows(chain, side)
except Exception as e:
    st.error(f'Option chain failed: {type(e).__name__}: {e}')
    st.stop()

if options.empty:
    st.warning('No option contracts returned for this selection.')
    st.stop()

spot = pd.to_numeric(pd.Series([x.get('underlying_spot_price') for x in chain if isinstance(x, dict)]), errors='coerce').dropna()
spot = float(spot.iloc[0]) if len(spot) else np.nan
atm = float(options.loc[(options['strike'] - spot).abs().idxmin(), 'strike']) if np.isfinite(spot) else float(options.iloc[len(options)//2]['strike'])
strike_choices = options['strike'].tolist()
default_idx = strike_choices.index(atm) if atm in strike_choices else len(strike_choices)//2
strike = st.selectbox('STRIKE PRICE', strike_choices, index=default_idx, format_func=lambda x: f'{x:,.0f}')
selected = options.loc[options['strike'] == strike].iloc[0]
instrument_key = selected['instrument_key']
if not instrument_key:
    st.error('Upstox did not return an instrument key for this contract.')
    st.stop()

try:
    quote_data = api_get_v3('/market-quote/quotes', {'instrument_key': instrument_key})
    quote = extract_quote(quote_data, instrument_key)
    bid, ask = depth_rows(quote)
except Exception as e:
    st.error(f'Order book failed: {type(e).__name__}: {e}')
    st.info('Upstox Full Market Quotes provides the top 5 displayed buy/sell depth levels for the selected option contract.')
    st.stop()

if bid.empty and ask.empty:
    st.warning('No displayed depth is currently available for this contract. Try an actively traded ATM or near-ATM strike.')
    st.stop()

ltp = float(quote.get('last_price', selected.get('ltp'))) if quote.get('last_price', selected.get('ltp')) is not None else np.nan
a = analysis(bid, ask, ltp)
now = datetime.now(ZoneInfo('Europe/London'))

cols = st.columns(7)
summary = [
    ('LTP', fmt(ltp), 'Last traded price', ''),
    ('BEST BID', fmt(a['best_bid']), 'Highest displayed bid', 'green'),
    ('BEST ASK', fmt(a['best_ask']), 'Lowest displayed ask', 'red'),
    ('SPREAD', fmt(a['spread'], 2), 'Ask − bid', 'amber'),
    ('BOOK IMBALANCE', f"{a['imbalance']*100:+.1f}%" if np.isfinite(a['imbalance']) else '—', '5-level bid vs ask qty', 'green' if a['imbalance'] > 0.05 else 'red' if a['imbalance'] < -0.05 else 'amber'),
    ('MICROPRICE', fmt(a['micro']), 'Depth-weighted fair pressure', 'green' if a['micro'] > a['mid'] else 'red' if a['micro'] < a['mid'] else 'amber'),
    ('LIQUIDITY', a['liquidity'], 'Displayed depth', ''),
]
for c, (name, value, note, cls) in zip(cols, summary):
    c.markdown(f'<div class="card"><div class="lab">{name}</div><div class="val {cls}">{value}</div><div class="sub">{note}</div></div>', unsafe_allow_html=True)

book_cls = a['cls']
regime = a['pressure']
st.markdown(f'<div class="book-card {book_cls}"><div class="book-title">ORDER BOOK READ • {side} {strike:,.0f} • {expiry.upper()}</div><div class="book-main {"green" if book_cls == "bull" else "red" if book_cls == "bear" else "amber"}">{regime}</div><div class="mini">Displayed depth is a liquidity snapshot, not a prediction. Strong imbalance can disappear quickly through cancellations or executions. Updated {now.strftime("%H:%M:%S %Z")}.</div></div>', unsafe_allow_html=True)

left, right = st.columns([3.1, 1.7], gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">LIVE MARKET DEPTH • TOP 5</div></div>', unsafe_allow_html=True)
    levels = max(len(bid), len(ask), 5)
    rows = []
    for i in range(levels):
        b = bid.iloc[i] if i < len(bid) else None
        s = ask.iloc[i] if i < len(ask) else None
        rows.append({
            'LEVEL': i + 1,
            'BID QTY': b['quantity'] if b is not None else np.nan,
            'BID PRICE': b['price'] if b is not None else np.nan,
            'ASK PRICE': s['price'] if s is not None else np.nan,
            'ASK QTY': s['quantity'] if s is not None else np.nan,
            'BID ORDERS': b['orders'] if b is not None else np.nan,
            'ASK ORDERS': s['orders'] if s is not None else np.nan,
        })
    depth_df = pd.DataFrame(rows)
    st.dataframe(depth_df, use_container_width=True, hide_index=True, height=300)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel"><div class="section"><div class="pt">DEPTH PROFILE</div></div>', unsafe_allow_html=True)
    fig = go.Figure()
    if not bid.empty:
        fig.add_trace(go.Bar(x=bid['price'], y=bid['quantity'], name='BIDS', marker_color='#00e676'))
    if not ask.empty:
        fig.add_trace(go.Bar(x=ask['price'], y=ask['quantity'], name='ASKS', marker_color='#ff5252'))
    if np.isfinite(ltp):
        fig.add_vline(x=ltp, line_dash='dash', annotation_text=f'LTP {ltp:,.2f}')
    fig.update_layout(height=360, template='plotly_dark', paper_bgcolor='#080a0b', plot_bgcolor='#080a0b', barmode='group', margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation='h'))
    fig.update_yaxes(title='Quantity')
    fig.update_xaxes(title='Price')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel"><div class="section"><div class="pt">ORDER FLOW INSIGHTS</div></div>', unsafe_allow_html=True)
    metrics = [
        ('5-LEVEL BID QTY', fmt(a['total_bid'], 0), 'Total displayed buy quantity'),
        ('5-LEVEL ASK QTY', fmt(a['total_ask'], 0), 'Total displayed sell quantity'),
        ('TOP-LEVEL IMBALANCE', f"{a['top_imb']*100:+.1f}%" if np.isfinite(a['top_imb']) else '—', 'Best bid vs best ask quantity'),
        ('BID WALL', fmt(a['bid_wall']), 'Largest displayed bid level'),
        ('ASK WALL', fmt(a['ask_wall']), 'Largest displayed ask level'),
        ('BID CONCENTRATION', f"{a['concentration_bid']*100:.1f}%" if np.isfinite(a['concentration_bid']) else '—', 'Top bid as % of bid depth'),
        ('ASK CONCENTRATION', f"{a['concentration_ask']*100:.1f}%" if np.isfinite(a['concentration_ask']) else '—', 'Top ask as % of ask depth'),
        ('MID → MICRO', f"{a['mid']:,.2f} → {a['micro']:,.2f}", 'Direction of depth pressure'),
    ]
    for name, value, desc in metrics:
        st.markdown(f'<div class="metric"><div class="name">{name}</div><div class="big">{value}</div><div class="desc">{desc}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="section"><div class="pt">HOW TO READ THIS PAGE</div></div><div class="mini"><b>Buy-side pressure:</b> more displayed bid quantity across the top five levels. <b>Sell-side pressure:</b> more displayed ask quantity. <b>Bid/ask wall:</b> the level with the largest displayed quantity. <b>Microprice:</b> a depth-weighted reference that shifts toward the side with less displayed liquidity. These are execution/liquidity signals, not guaranteed directional signals. The page uses Upstox Full Market Quotes top-5 depth; it does not claim to reconstruct hidden orders or the full exchange order book.</div></div>', unsafe_allow_html=True)
