import numpy as np
import pandas as pd


def market_structure(df, lookback=5):
    d=df.copy()
    if len(d)<3:return d, {'trend':'NEUTRAL','score':0,'setup':'INSUFFICIENT DATA'}
    w=max(2,min(lookback,len(d)//3))
    d['swing_high']=d.high.eq(d.high.rolling(2*w+1,center=True,min_periods=1).max())
    d['swing_low']=d.low.eq(d.low.rolling(2*w+1,center=True,min_periods=1).min())
    last=float(d.close.iloc[-1]); ema9=float(d.ema9.iloc[-1]); ema20=float(d.ema20.iloc[-1]); ema50=float(d.ema50.iloc[-1]); vwap=float(d.vwap.iloc[-1]) if np.isfinite(d.vwap.iloc[-1]) else last
    score=0
    score += 1 if last>ema20 else -1
    score += 1 if ema9>ema20 else -1
    score += 1 if ema20>ema50 else -1
    score += 1 if last>vwap else -1
    trend='BULLISH' if score>=3 else 'BEARISH' if score<=-3 else 'NEUTRAL'
    recent=d.tail(20); high=float(recent.high.max()); low=float(recent.low.min())
    location='BREAKOUT' if last>high*0.999 and last>ema20 else 'BREAKDOWN' if last<low*1.001 and last<ema20 else 'RANGE'
    return d, {'trend':trend,'score':score,'setup':location,'range_high':high,'range_low':low}


def signal_score(structure, patterns):
    score=int(structure.get('score',0))
    for _,_,direction,_ in patterns[-10:]:
        if direction=='bullish': score += 1
        elif direction=='bearish': score -= 1
    return max(-5,min(5,score))
