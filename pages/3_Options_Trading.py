# Options Trading page
import os
from datetime import date
import numpy as np
import pandas as pd
import requests
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title='Nifty Vision • Options', page_icon='◈', layout='wide')
TOKEN=st.secrets.get('UPSTOX_ACCESS_TOKEN',os.getenv('UPSTOX_ACCESS_TOKEN',''))
UNDERLYING='NSE_INDEX|Nifty 50'
EXPIRIES=['current_week','next_week','current_month','next_month']

st.markdown('''<style>
.stApp{background:#050607;color:#f5f7fa}.block-container{max-width:1880px;padding:2rem 2.2rem 3rem!important}[data-testid="stSidebar"]{background:#080a0c;border-right:1px solid #20252b}
.kicker{font-size:.62rem;font-weight:900;letter-spacing:2.4px;color:#6f7882;text-transform:uppercase}.title{font-size:2.55rem;font-weight:950;letter-spacing:-2px}.sub,.note{font-size:.68rem;color:#89929b}.status{display:inline-block;border:1px solid #30363d;border-radius:999px;padding:4px 9px;font-size:.57rem;font-weight:850;color:#aeb6bf}.card{background:linear-gradient(145deg,#101316,#0a0c0e);border:1px solid #252b31;border-radius:14px;padding:14px 16px;min-height:90px}.lab{font-size:.57rem;color:#737d87;font-weight:900;letter-spacing:1.4px}.val{font-size:1.32rem;font-weight:950;margin-top:7px}.green{color:#00e676}.red{color:#ff5252}.amber{color:#ffc107}.panel{background:linear-gradient(145deg,#0d1012,#090b0d);border:1px solid #252b31;border-radius:16px;padding:16px;margin-bottom:14px}.pt{font-size:.78rem;font-weight:1000;letter-spacing:1.8px;color:#fff;text-transform:uppercase}.section{border-bottom:1px solid #20262b;padding-bottom:10px;margin-bottom:13px}.setup{border-radius:16px;padding:18px;border:1px solid #ffc107;background:#171307}.setup.bull{border-color:#00e676;background:#091b12}.setup.bear{border-color:#ff5252;background:#1b0b0b}.setup-title{font-size:.58rem;font-weight:900;letter-spacing:1.8px}.setup-main{font-size:1.55rem;font-weight:950;margin:7px 0}.mini{font-size:.64rem;color:#9aa3ad}.indicator{background:#0a0d10;border:1px solid #20262c;border-radius:11px;padding:12px;margin-bottom:8px}.indicator .name{font-size:.58rem;font-weight:900;letter-spacing:1.2px;color:#77818b}.indicator .big{font-size:1.15rem;font-weight:950;margin-top:4px}.indicator .desc{font-size:.6rem;color:#8d969f;margin-top:3px}
</style>''',unsafe_allow_html=True)

def api_get(path,params):
    r=requests.get('https://api.upstox.com/v2'+path,params=params,headers={'Accept':'application/json','Authorization':f'Bearer {TOKEN}'},timeout=20)
    try:b=r.json()
    except Exception:b={}
    if r.status_code>=400: raise RuntimeError(f"HTTP {r.status_code}: {b.get('errors') or b.get('message') or r.text[:300]}")
    if b.get('status')!='success': raise RuntimeError(b.get('errors') or b.get('message') or 'Upstox API returned an error')
    return b.get('data',[])

def as_rows(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for k in ('data','items','results'):
            if isinstance(data.get(k),list): return data[k]
    return []

def resolve_expiry(keyword):
    rows=as_rows(api_get('/option/contract',{'instrument_key':UNDERLYING}))
    dates=sorted({str(x.get('expiry')) for x in rows if isinstance(x,dict) and x.get('expiry') and str(x.get('expiry'))>=date.today().isoformat()})
    if not dates: raise RuntimeError('No future NIFTY option expiries returned by Upstox.')
    if keyword=='current_week': return dates[0]
    if keyword=='next_week': return dates[min(1,len(dates)-1)]
    if keyword=='current_month': return [d for d in dates if d[:7]==dates[0][:7]][-1]
    if keyword=='next_month':
        months=sorted({d[:7] for d in dates if d[:7]>dates[0][:7]})
        return [d for d in dates if d[:7]==months[0]][-1] if months else dates[-1]
    return keyword

def load_chain(expiry):
    raw=api_get('/option/chain',{'instrument_key':UNDERLYING,'expiry_date':expiry})
    rows=as_rows(raw)
    if rows: return rows,expiry
    actual=resolve_expiry(expiry) if expiry in EXPIRIES else expiry
    rows=as_rows(api_get('/option/chain',{'instrument_key':UNDERLYING,'expiry_date':actual}))
    if not rows: raise RuntimeError(f'No NIFTY option-chain rows returned for {actual}.')
    return rows,actual

def flatten(rows):
    out=[]
    for x in rows:
        if not isinstance(x,dict): continue
        strike=x.get('strike_price')
        if strike is None: continue
        c=x.get('call_options') or {};p=x.get('put_options') or {}
        cm=c.get('market_data') or {};pm=p.get('market_data') or {};cg=c.get('option_greeks') or {};pg=p.get('option_greeks') or {}
        out.append({'strike':float(strike),'spot':pd.to_numeric(x.get('underlying_spot_price'),errors='coerce'),'call_ltp':cm.get('ltp'),'call_oi':cm.get('oi',0),'call_prev_oi':cm.get('prev_oi',0),'call_vol':cm.get('volume',0),'call_iv':cg.get('iv'),'call_delta':cg.get('delta'),'call_gamma':cg.get('gamma'),'call_theta':cg.get('theta'),'call_vega':cg.get('vega'),'put_ltp':pm.get('ltp'),'put_oi':pm.get('oi',0),'put_prev_oi':pm.get('prev_oi',0),'put_vol':pm.get('volume',0),'put_iv':pg.get('iv'),'put_delta':pg.get('delta'),'put_gamma':pg.get('gamma'),'put_theta':pg.get('theta'),'put_vega':pg.get('vega')})
    if not out: raise RuntimeError('Upstox returned data but no valid strike_price rows were found.')
    return pd.DataFrame(out).sort_values('strike').reset_index(drop=True)

def safe_num(x,d=2):
    try: return '—' if pd.isna(x) else f'{float(x):,.{d}f}'
    except Exception: return '—'

def max_pain(df):
    strikes=df['strike'].to_numpy();co=pd.to_numeric(df['call_oi'],errors='coerce').fillna(0).to_numpy();po=pd.to_numeric(df['put_oi'],errors='coerce').fillna(0).to_numpy()
    if len(strikes)==0:return np.nan
    losses=[np.sum(np.maximum(s-strikes,0)*co)+np.sum(np.maximum(strikes-s,0)*po) for s in strikes]
    return float(strikes[int(np.argmin(losses))])

st_autorefresh(interval=30000,key='options_refresh')
st.markdown('<div class="kicker">NIFTY 50 • DERIVATIVES</div><div class="title">Options Trading</div><div class="sub">Option chain • OI intelligence • IV • Greeks • support / resistance • option indicators</div>',unsafe_allow_html=True)
st.divider()
if not TOKEN: st.error('Add UPSTOX_ACCESS_TOKEN to Streamlit Secrets.');st.stop()
c1,c2,c3=st.columns([1.1,1.1,2.8])
with c1: expiry=st.selectbox('EXPIRY',EXPIRIES,index=0)
with c2: window=st.select_slider('STRIKES AROUND ATM',options=[5,7,10,15,20],value=10)
with c3: st.caption('Upstox Option Chain • refreshes every 30 seconds')
try:
    rows,actual=load_chain(expiry);df=flatten(rows)
except Exception as e:
    st.error(f'Option chain failed: {type(e).__name__}: {e}')
    st.info('If the selected relative expiry has no rows, Nifty Vision resolves the active NIFTY expiry date and retries once.')
    st.stop()
if df.empty or 'strike' not in df.columns: st.warning('No valid option-chain strikes returned.');st.stop()
st.markdown(f'<span class="status">EXPIRY {actual}</span>',unsafe_allow_html=True)
spot=float(pd.to_numeric(df['spot'],errors='coerce').dropna().iloc[0]);atm_idx=int((df['strike']-spot).abs().idxmin());atm=float(df.loc[atm_idx,'strike']);lo=max(0,atm_idx-window);hi=min(len(df),atm_idx+window+1);view=df.iloc[lo:hi].copy()
ce=pd.to_numeric(view.call_oi,errors='coerce').fillna(0).sum();pe=pd.to_numeric(view.put_oi,errors='coerce').fillna(0).sum();pcr=pe/ce if ce else np.nan
ce_wall=view[view.strike>=spot].sort_values('call_oi',ascending=False).head(1);pe_wall=view[view.strike<=spot].sort_values('put_oi',ascending=False).head(1);cw=float(ce_wall.strike.iloc[0]) if len(ce_wall) else np.nan;pw=float(pe_wall.strike.iloc[0]) if len(pe_wall) else np.nan
ce_doi=(pd.to_numeric(view.call_oi,errors='coerce').fillna(0)-pd.to_numeric(view.call_prev_oi,errors='coerce').fillna(0)).sum();pe_doi=(pd.to_numeric(view.put_oi,errors='coerce').fillna(0)-pd.to_numeric(view.put_prev_oi,errors='coerce').fillna(0)).sum();flow='CALL WRITING' if ce_doi>pe_doi*1.2 else 'PUT WRITING' if pe_doi>ce_doi*1.2 else 'BALANCED'
vol_ce=pd.to_numeric(view.call_vol,errors='coerce').fillna(0).sum();vol_pe=pd.to_numeric(view.put_vol,errors='coerce').fillna(0).sum();pcr_vol=vol_pe/vol_ce if vol_ce else np.nan
atmrow=df.iloc[atm_idx];atm_iv=np.nanmean([pd.to_numeric(atmrow.call_iv,errors='coerce'),pd.to_numeric(atmrow.put_iv,errors='coerce')]);iv_skew=pd.to_numeric(atmrow.put_iv,errors='coerce')-pd.to_numeric(atmrow.call_iv,errors='coerce') if pd.notna(atmrow.put_iv) and pd.notna(atmrow.call_iv) else np.nan
pcr_score=1 if pcr>=1.05 else -1 if pcr<=.85 else 0;flow_score=1 if flow=='PUT WRITING' else -1 if flow=='CALL WRITING' else 0;wall_score=1 if np.isfinite(pw) and (not np.isfinite(cw) or spot-pw<cw-spot) else -1 if np.isfinite(cw) else 0;score=pcr_score+flow_score+wall_score;setup='BULLISH' if score>=2 else 'BEARISH' if score<=-2 else 'NEUTRAL';setup_cls='green' if setup=='BULLISH' else 'red' if setup=='BEARISH' else 'amber';setup_box='bull' if setup=='BULLISH' else 'bear' if setup=='BEARISH' else ''
gamma=np.nanmean([pd.to_numeric(atmrow.call_gamma,errors='coerce'),pd.to_numeric(atmrow.put_gamma,errors='coerce')]);theta=np.nanmean([pd.to_numeric(atmrow.call_theta,errors='coerce'),pd.to_numeric(atmrow.put_theta,errors='coerce')]);vega=np.nanmean([pd.to_numeric(atmrow.call_vega,errors='coerce'),pd.to_numeric(atmrow.put_vega,errors='coerce')]);delta=np.nanmean([pd.to_numeric(atmrow.call_delta,errors='coerce'),abs(pd.to_numeric(atmrow.put_delta,errors='coerce'))]);mp=max_pain(df)
cols=st.columns(7)
items=[('NIFTY',safe_num(spot),'Spot',''),('ATM',safe_num(atm,0),'Nearest strike',''),('PCR OI',safe_num(pcr),'Put OI / Call OI',''),('PCR VOL',safe_num(pcr_vol),'Put volume / Call volume',''),('ATM IV',safe_num(atm_iv),'Average ATM CE / PE IV',''),('IV SKEW',safe_num(iv_skew),'Put IV − Call IV','green' if np.isfinite(iv_skew) and iv_skew<0 else 'red' if np.isfinite(iv_skew) and iv_skew>0 else 'amber'),('MAX PAIN',safe_num(mp,0),'Full-chain estimate','amber')]
for c,(a,b,note,cl) in zip(cols,items): c.markdown(f'<div class="card"><div class="lab">{a}</div><div class="val {cl}">{b}</div><div class="note">{note}</div></div>',unsafe_allow_html=True)
left,right=st.columns([3.35,1.65],gap='large')
with left:
    st.markdown('<div class="panel"><div class="section"><div class="pt">OPTION CHAIN</div></div>',unsafe_allow_html=True)
    disp=view[['strike','call_oi','call_ltp','call_iv','call_delta','put_delta','put_iv','put_ltp','put_oi']].copy();disp.columns=['STRIKE','CE OI','CE LTP','CE IV','CE Δ','PE Δ','PE IV','PE LTP','PE OI'];st.dataframe(disp,use_container_width=True,hide_index=True,height=500);st.markdown('</div>',unsafe_allow_html=True)
with right:
    st.markdown(f'<div class="setup {setup_box}"><div class="setup-title">OPTIONS MARKET REGIME</div><div class="setup-main {setup_cls}">{setup}</div><div class="mini">Evidence {score:+d}/3 • PCR {safe_num(pcr)} • {flow}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="section"><div class="pt">OPTION INDICATORS</div></div>',unsafe_allow_html=True)
    inds=[('ATM DELTA',safe_num(delta),'Average absolute ATM delta'),('GAMMA',safe_num(gamma,5),'ATM gamma sensitivity'),('THETA',safe_num(theta),'Average ATM time decay'),('VEGA',safe_num(vega),'ATM IV sensitivity'),('PUT SUPPORT',safe_num(pw,0),'Largest PE OI below spot'),('CALL RESISTANCE',safe_num(cw,0),'Largest CE OI above spot')]
    for name,val,desc in inds: st.markdown(f'<div class="indicator"><div class="name">{name}</div><div class="big">{val}</div><div class="desc">{desc}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
st.markdown('<div class="panel"><div class="section"><div class="pt">OI MAP • LIQUIDITY STRUCTURE</div></div>',unsafe_allow_html=True)
fig=go.Figure();fig.add_trace(go.Bar(x=view.strike,y=pd.to_numeric(view.call_oi,errors='coerce').fillna(0),name='CE OI'));fig.add_trace(go.Bar(x=view.strike,y=-pd.to_numeric(view.put_oi,errors='coerce').fillna(0),name='PE OI'));fig.add_vline(x=spot,line_dash='dash',annotation_text=f'SPOT {spot:,.0f}');fig.update_layout(height=380,barmode='relative',template='plotly_dark',paper_bgcolor='#080a0b',plot_bgcolor='#080a0b',margin=dict(l=10,r=10,t=10,b=10),legend=dict(orientation='h'));st.plotly_chart(fig,use_container_width=True);st.markdown('</div>',unsafe_allow_html=True)
