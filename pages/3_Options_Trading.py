import os
from datetime import date
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title='Nifty Vision • Options', page_icon='◈', layout='wide')
TOKEN = st.secrets.get('UPSTOX_ACCESS_TOKEN', os.getenv('UPSTOX_ACCESS_TOKEN', ''))
UNDERLYING = 'NSE_INDEX|Nifty 50'
EXPIRIES = ['current_week', 'next_week', 'current_month', 'next_month']

st.markdown('''<style>
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}
[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px;line-height:1;margin:.35rem 0 .45rem}.sub{font-size:.72rem;color:#737d87}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;letter-spacing:.8px;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px;text-transform:uppercase}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.note{font-size:.68rem;color:#89929b;line-height:1.5}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.setup{border-radius:16px;padding:18px;border:1px solid #ffc107;background:linear-gradient(135deg,#191607,#0d0c09);box-shadow:0 0 28px rgba(255,193,7,.08)}.setup.bull{border-color:#00e676;background:linear-gradient(135deg,#091b12,#0a0d0c);box-shadow:0 0 28px rgba(0,230,118,.08)}.setup.bear{border-color:#ff5252;background:linear-gradient(135deg,#1b0b0b,#0d0a0a);box-shadow:0 0 28px rgba(255,82,82,.08)}.setup-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px;color:#9ba4ad}.setup-main{font-size:1.55rem;font-weight:950;margin:7px 0}.mini{font-size:.64rem;color:#9aa3ad;margin-top:3px}.tag{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:3px 7px;font-size:.55rem;font-weight:850;margin:2px 3px 2px 0}.tag.green{border-color:#176b43}.tag.red{border-color:#6b2222}.tag.amber{border-color:#6b5710}
</style>''', unsafe_allow_html=True)

def api_get(path, params):
    r = requests.get('https://api.upstox.com/v2' + path, params=params, headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'}, timeout=20)
    try:
        body = r.json()
    except Exception:
        body = {}
    if r.status_code >= 400:
        detail = body.get('errors') or body.get('message') or r.text[:300]
        raise RuntimeError(f'HTTP {r.status_code}: {detail}')
    if body.get('status') != 'success':
        raise RuntimeError(body.get('errors') or body.get('message') or 'Upstox API returned an error')
    data = body.get('data', [])
    return data

def as_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('data','items','results'):
            if isinstance(data.get(key), list):
                return data[key]
    return []

def resolve_expiry(keyword):
    """Resolve a relative expiry to a real YYYY-MM-DD date when the chain endpoint returns no rows."""
    rows = as_rows(api_get('/option/contract', {'instrument_key': UNDERLYING}))
    dates = sorted({str(x.get('expiry')) for x in rows if x.get('expiry')})
    today = date.today().isoformat()
    dates = [d for d in dates if d >= today]
    if not dates:
        raise RuntimeError('Upstox returned no future NIFTY option expiries.')
    if keyword == 'current_week':
        return dates[0]
    if keyword == 'next_week':
        return dates[1] if len(dates) > 1 else dates[0]
    if keyword == 'current_month':
        ym = dates[0][:7]
        same = [d for d in dates if d[:7] == ym]
        return same[-1] if same else dates[0]
    if keyword == 'next_month':
        ym = dates[0][:7]
        months = sorted({d[:7] for d in dates if d[:7] > ym})
        if months:
            return [d for d in dates if d[:7] == months[0]][-1]
        return dates[-1]
    return keyword

def load_chain(expiry):
    rows = as_rows(api_get('/option/chain', {'instrument_key': UNDERLYING, 'expiry_date': expiry}))
    if rows:
        return rows, expiry
    # Some sessions can return an empty chain for a relative keyword after an expiry rollover.
    # Resolve it to the actual active contract date and retry once.
    actual = resolve_expiry(expiry) if expiry in EXPIRIES else expiry
    rows = as_rows(api_get('/option/chain', {'instrument_key': UNDERLYING, 'expiry_date': actual}))
    if not rows:
        raise RuntimeError(f'No NIFTY option-chain rows returned for {actual}.')
    return rows, actual

def flatten(rows):
    out=[]
    for x in rows:
        if not isinstance(x, dict) or x.get('strike_price') is None:
            continue
        c=x.get('call_options') or {}; p=x.get('put_options') or {}
        cm=c.get('market_data') or {}; pm=p.get('market_data') or {}
        cg=c.get('option_greeks') or {}; pg=p.get('option_greeks') or {}
        out.append({'strike':float(x.get('strike_price')),'expiry':x.get('expiry'),'spot':float(x.get('underlying_spot_price',np.nan)),'call_ltp':cm.get('ltp'),'call_oi':cm.get('oi',0),'call_prev_oi':cm.get('prev_oi',0),'call_vol':cm.get('volume',0),'call_bid':cm.get('bid_price'),'call_ask':cm.get('ask_price'),'call_iv':cg.get('iv'),'call_delta':cg.get('delta'),'put_ltp':pm.get('ltp'),'put_oi':pm.get('oi',0),'put_prev_oi':pm.get('prev_oi',0),'put_vol':pm.get('volume',0),'put_bid':pm.get('bid_price'),'put_ask':pm.get('ask_price'),'put_iv':pg.get('iv'),'put_delta':pg.get('delta')})
    if not out:
        raise RuntimeError('Upstox returned option-chain data, but no rows contained strike_price.')
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)

def max_pain(df):
    strikes=df.strike.values; call_oi=df.call_oi.fillna(0).values; put_oi=df.put_oi.fillna(0).values
    pain=[float(np.sum(np.maximum(s-strikes,0)*call_oi)+np.sum(np.maximum(strikes-s,0)*put_oi)) for s in strikes]
    return float(strikes[int(np.argmin(pain))]) if len(strikes) else np.nan

def fmt(v): return '—' if pd.isna(v) else f'{v:,.0f}'

st_autorefresh(interval=30000, key='options_refresh')
st.markdown('<div class="kicker">NIFTY 50 • DERIVATIVES</div><div class="title">Options Trading</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Live option chain • OI intelligence • IV • Greeks • support / resistance • OI flow</div>', unsafe_allow_html=True)
st.divider()
if not TOKEN: st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.'); st.stop()

c1,c2,c3=st.columns([1.1,1.1,2.8])
with c1: expiry=st.selectbox('EXPIRY', EXPIRIES, index=0)
with c2: window=st.select_slider('STRIKES AROUND ATM', options=[5,7,10,15,20], value=10)
with c3: st.caption('Data source: Upstox Option Chain API • refreshes every 30 seconds')
try:
    rows,actual_expiry=load_chain(expiry)
    df=flatten(rows)
except Exception as e:
    st.error(f'Option chain failed: {type(e).__name__}: {e}')
    st.info('The page now retries relative expiries using the active NIFTY expiry date when Upstox returns an empty chain.')
    st.stop()
if df.empty or 'strike' not in df.columns:
    st.warning('No option-chain data returned for this expiry.'); st.stop()
st.markdown(f'<span class="status">EXPIRY {actual_expiry}</span>', unsafe_allow_html=True)

spot=float(df.spot.dropna().iloc[0]); atm_idx=int((df.strike-spot).abs().idxmin()); atm=float(df.loc[atm_idx,'strike']); lo=max(0,atm_idx-window); hi=min(len(df),atm_idx+window+1); view=df.iloc[lo:hi].copy()
total_ce=view.call_oi.fillna(0).sum(); total_pe=view.put_oi.fillna(0).sum(); pcr=(total_pe/total_ce) if total_ce else np.nan; mp=max_pain(df)
ce_res=view.loc[view.strike>=spot].sort_values('call_oi',ascending=False).head(1); pe_sup=view.loc[view.strike<=spot].sort_values('put_oi',ascending=False).head(1); ce_wall=float(ce_res.strike.iloc[0]) if not ce_res.empty else np.nan; pe_wall=float(pe_sup.strike.iloc[0]) if not pe_sup.empty else np.nan
ce_chg=(view.call_oi.fillna(0)-view.call_prev_oi.fillna(0)).sum(); pe_chg=(view.put_oi.fillna(0)-view.put_prev_oi.fillna(0)).sum(); flow='CALL WRITING' if ce_chg>pe_chg*1.2 else 'PUT WRITING' if pe_chg>ce_chg*1.2 else 'BALANCED'; flow_cls='red' if flow=='CALL WRITING' else 'green' if flow=='PUT WRITING' else 'amber'
pcr_score=1 if pcr>=1.05 else -1 if pcr<=0.85 else 0; flow_score=-1 if flow=='CALL WRITING' else 1 if flow=='PUT WRITING' else 0; wall_score=1 if np.isfinite(pe_wall) and spot-pe_wall < (ce_wall-spot if np.isfinite(ce_wall) else 1e9) else -1 if np.isfinite(ce_wall) else 0; setup_score=pcr_score+flow_score+wall_score; setup='BULLISH' if setup_score>=2 else 'BEARISH' if setup_score<=-2 else 'NEUTRAL'; setup_cls='bull' if setup=='BULLISH' else 'bear' if setup=='BEARISH' else ''; setup_color='green' if setup=='BULLISH' else 'red' if setup=='BEARISH' else 'amber'
view['CE ΔOI']=view.call_oi.fillna(0)-view.call_prev_oi.fillna(0); view['PE ΔOI']=view.put_oi.fillna(0)-view.put_prev_oi.fillna(0)

cols=st.columns(7)
for c,(a,b,note,cl) in zip(cols,[('NIFTY',f'{spot:,.2f}','Spot',''),('ATM',f'{atm:,.0f}','Nearest strike',''),('PCR',f'{pcr:.2f}' if np.isfinite(pcr) else '—','Visible-window OI',''),('MAX PAIN',f'{mp:,.0f}' if np.isfinite(mp) else '—','Full chain',''),('CALL WALL',fmt(ce_wall),'Highest CE OI above spot','red'),('PUT WALL',fmt(pe_wall),'Highest PE OI below spot','green'),('FLOW',flow,'OI change comparison',flow_cls)]): c.markdown(f"<div class='card'><div class='lab'>{a}</div><div class='val {cl}'>{b}</div><div class='note'>{note}</div></div>",unsafe_allow_html=True)

left,right=st.columns([3.45,1.55],gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">OPTION CHAIN</div></div>',unsafe_allow_html=True)
    display=view[['strike','call_oi','CE ΔOI','call_vol','call_ltp','call_iv','put_ltp','put_iv','put_vol','PE ΔOI','put_oi']].copy(); display.columns=['STRIKE','CE OI','CE ΔOI','CE VOL','CE LTP','CE IV','PE LTP','PE IV','PE VOL','PE ΔOI','PE OI']
    for c in ['STRIKE','CE OI','CE ΔOI','CE VOL','PE VOL','PE ΔOI','PE OI']: display[c]=display[c].fillna(0).astype(int)
    for c in ['CE LTP','PE LTP','CE IV','PE IV']: display[c]=pd.to_numeric(display[c],errors='coerce').round(2)
    st.dataframe(display,use_container_width=True,hide_index=True,height=560,column_config={'STRIKE':st.column_config.NumberColumn(format='%d'),'CE OI':st.column_config.NumberColumn(format='%,d'),'PE OI':st.column_config.NumberColumn(format='%,d'),'CE ΔOI':st.column_config.NumberColumn(format='%+,d'),'PE ΔOI':st.column_config.NumberColumn(format='%+,d'),'CE VOL':st.column_config.NumberColumn(format='%,d'),'PE VOL':st.column_config.NumberColumn(format='%,d')})
    st.markdown('</div>',unsafe_allow_html=True)
with right:
    st.markdown(f'<div class="setup {setup_cls}"><div class="setup-title">OPTIONS SETUP</div><div class="setup-main {setup_color}">{setup}</div><div class="mini">PCR: {pcr:.2f} • Flow: {flow}</div><div class="mini">Evidence score: {setup_score:+d} / 3</div><div style="margin-top:9px"><span class="tag {setup_color}">OI FLOW</span><span class="tag {setup_color}">{flow}</span></div></div>',unsafe_allow_html=True)
    st.markdown(f'<div class="panel"><div class="section"><div class="pt">OI SUPPORT / RESISTANCE</div></div><div class="val green">PUT SUPPORT • {fmt(pe_wall)}</div><div class="note">Largest PE open interest below spot in the selected window.</div><br><div class="val red">CALL RESISTANCE • {fmt(ce_wall)}</div><div class="note">Largest CE open interest above spot in the selected window.</div><br><div class="val amber">MAX PAIN • {fmt(mp)}</div><div class="note">Strike with minimum aggregate expiry payoff using current OI.</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="section"><div class="pt">OI CHANGE</div></div>',unsafe_allow_html=True)
    oi_df=view[['strike']].copy(); oi_df['ce_change']=view['CE ΔOI']; oi_df['pe_change']=view['PE ΔOI']; top_ce=oi_df.loc[oi_df.ce_change.idxmax()]; top_pe=oi_df.loc[oi_df.pe_change.idxmax()]
    st.markdown(f'<div class="note">Largest CE OI addition: <b>{top_ce.strike:.0f}</b> ({top_ce.ce_change:+,.0f})<br>Largest PE OI addition: <b>{top_pe.strike:.0f}</b> ({top_pe.pe_change:+,.0f})</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

st.markdown('<div class="panel"><div class="section"><div class="pt">OI MAP • LIQUIDITY STRUCTURE</div></div>',unsafe_allow_html=True)
chart=pd.DataFrame({'strike':view.strike,'CE OI':view.call_oi.fillna(0),'PE OI':-view.put_oi.fillna(0)}); fig=go.Figure(); fig.add_trace(go.Bar(x=chart.strike,y=chart['CE OI'],name='CE OI')); fig.add_trace(go.Bar(x=chart.strike,y=chart['PE OI'],name='PE OI')); fig.add_vline(x=spot,line_dash='dash',annotation_text=f'SPOT {spot:,.0f}'); fig.update_layout(height=390,barmode='relative',template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',margin=dict(l=10,r=10,t=10,b=10),xaxis_title='Strike',yaxis_title='Open Interest',legend=dict(orientation='h')); st.plotly_chart(fig,use_container_width=True)
st.markdown('</div>',unsafe_allow_html=True)
