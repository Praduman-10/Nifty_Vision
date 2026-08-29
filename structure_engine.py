import numpy as np
import pandas as pd


def detect_structure(df, swing=5):
    d=df.copy()
    if len(d)<max(10,swing*2+2):
        return {'trend':'NEUTRAL','events':[],'latest':'INSUFFICIENT DATA','confidence':'LOW'}
    highs=d.high.rolling(swing*2+1,center=True).max()
    lows=d.low.rolling(swing*2+1,center=True).min()
    hi_idx=d.index[d.high.eq(highs).fillna(False)].tolist()
    lo_idx=d.index[d.low.eq(lows).fillna(False)].tolist()
    events=[]
    for ids,kind in ((hi_idx,'HIGH'),(lo_idx,'LOW')):
        for j in range(1,len(ids)):
            prev=d.loc[ids[j-1]]; cur=d.loc[ids[j]]
            if kind=='HIGH': label='HH' if cur.high>prev.high else 'LH'
            else: label='HL' if cur.low>prev.low else 'LL'
            events.append({'index':ids[j],'type':label,'price':float(cur.high if kind=='HIGH' else cur.low)})
    recent=events[-6:]
    labels=[e['type'] for e in recent]
    bull=sum(x in ('HH','HL') for x in labels); bear=sum(x in ('LH','LL') for x in labels)
    trend='BULLISH' if bull>bear+1 else 'BEARISH' if bear>bull+1 else 'NEUTRAL'
    last=float(d.close.iloc[-1]); last_high=max((e['price'] for e in recent if e['type'] in ('HH','LH')),default=last); last_low=min((e['price'] for e in recent if e['type'] in ('HL','LL')),default=last)
    events2=list(recent)
    if last>last_high: events2.append({'index':d.index[-1],'type':'BOS UP','price':last})
    elif last<last_low: events2.append({'index':d.index[-1],'type':'BOS DOWN','price':last})
    latest=events2[-1]['type'] if events2 else 'RANGE'
    confidence='HIGH' if abs(bull-bear)>=3 else 'MEDIUM' if abs(bull-bear)>=1 else 'LOW'
    return {'trend':trend,'events':events2[-8:],'latest':latest,'confidence':confidence}
