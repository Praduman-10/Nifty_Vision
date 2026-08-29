import numpy as np
import pandas as pd
from market_intelligence import market_structure

TIMEFRAMES = ['1 day','1 hour','15 min','5 min']

def analyse_frame(df, frame):
    if df is None or len(df) < 3:
        return {'frame':frame,'trend':'N/A','setup':'INSUFFICIENT DATA','score':0,'alignment':'—'}
    d=df.copy()
    for span in (9,20,50):
        d[f'ema{span}']=d.close.ewm(span=span,adjust=False,min_periods=1).mean()
    if 'vwap' not in d or d.vwap.isna().all(): d['vwap']=d.close
    d, s=market_structure(d)
    return {'frame':frame,'trend':s['trend'],'setup':s['setup'],'score':s['score'],'alignment':'BULLISH' if s['score']>=3 else 'BEARISH' if s['score']<=-3 else 'NEUTRAL'}

def overall(results):
    valid=[r for r in results if r['trend']!='N/A']
    if not valid:return {'trend':'N/A','aligned':0,'total':0,'score':0,'text':'Waiting for multi-timeframe data'}
    score=sum(r['score'] for r in valid)
    bull=sum(r['trend']=='BULLISH' for r in valid); bear=sum(r['trend']=='BEARISH' for r in valid)
    trend='BULLISH' if bull>bear else 'BEARISH' if bear>bull else 'MIXED'
    aligned=max(bull,bear)
    return {'trend':trend,'aligned':aligned,'total':len(valid),'score':score,'text':f'{trend} — {aligned}/{len(valid)} timeframes aligned'}
