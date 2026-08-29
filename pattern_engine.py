import numpy as np
import pandas as pd

BULLISH = {'HAMMER','BULLISH ENGULFING','MORNING STAR','PIERCING LINE'}
BEARISH = {'SHOOTING STAR','BEARISH ENGULFING','EVENING STAR','DARK CLOUD COVER'}

def _row(d,i): return d.iloc[i]
def detect_patterns(d):
    out=[]
    for i in range(2,len(d)):
        a,b,c=_row(d,i-2),_row(d,i-1),_row(d,i)
        body=max(abs(c.close-c.open),1e-9); rng=max(c.high-c.low,1e-9)
        lo=min(c.open,c.close)-c.low; up=c.high-max(c.open,c.close)
        name=None; direction='neutral'; meaning='Indecision'
        if body/rng<.15: name='DOJI'; meaning='Indecision / balance'
        elif lo>=body*2 and up<=body*.8 and c.close>=c.open: name='HAMMER'; direction='bullish'; meaning='Bullish rejection of lower prices'
        elif up>=body*2 and lo<=body*.8 and c.close<=c.open: name='SHOOTING STAR'; direction='bearish'; meaning='Bearish rejection of higher prices'
        elif b.close<b.open and c.close>c.open and c.open<=b.close and c.close>=b.open: name='BULLISH ENGULFING'; direction='bullish'; meaning='Strong bullish reversal'
        elif b.close>b.open and c.close<c.open and c.open>=b.close and c.close<=b.open: name='BEARISH ENGULFING'; direction='bearish'; meaning='Strong bearish reversal'
        elif a.close<a.open and abs(b.close-b.open)/max(b.high-b.low,1e-9)<.35 and c.close>c.open and c.close>(a.open+a.close)/2: name='MORNING STAR'; direction='bullish'; meaning='Three-candle bullish reversal'
        elif a.close>a.open and abs(b.close-b.open)/max(b.high-b.low,1e-9)<.35 and c.close<c.open and c.close<(a.open+a.close)/2: name='EVENING STAR'; direction='bearish'; meaning='Three-candle bearish reversal'
        elif b.close<b.open and c.close>c.open and c.open<b.close and c.close>(b.open+b.close)/2: name='PIERCING LINE'; direction='bullish'; meaning='Bullish recovery after selling'
        elif b.close>b.open and c.close<c.open and c.open>b.close and c.close<(b.open+b.close)/2: name='DARK CLOUD COVER'; direction='bearish'; meaning='Bearish reversal after buying'
        if name:
            score=1
            if direction=='bullish' and c.close>c.ema20: score+=1
            if direction=='bearish' and c.close<c.ema20: score+=1
            if 'vwap' in d and np.isfinite(c.vwap):
                if direction=='bullish' and c.close>c.vwap: score+=1
                if direction=='bearish' and c.close<c.vwap: score+=1
            confidence='HIGH' if score>=3 else 'MEDIUM' if score==2 else 'LOW'
            out.append({'index':i,'name':name,'direction':direction,'meaning':meaning,'confidence':confidence,'score':score})
    # Keep one visible instance of each pattern type, preferring the latest occurrence.
    latest={p['name']:p for p in out}
    return list(latest.values())
