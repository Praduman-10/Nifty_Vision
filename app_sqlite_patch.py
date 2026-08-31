"""Dashboard data helpers with a live-first fallback."""
import pandas as pd
from data_service import get_market_data, TIMEFRAMES


def load_for_dashboard(frame_label, candles=500):
    """Return current market candles, even when the local SQLite cache starts empty."""
    if frame_label not in TIMEFRAMES:
        raise ValueError(f'Unsupported timeframe: {frame_label}')
    d, source = get_market_data(frame_label, limit=candles)
    if d is None or d.empty:
        return pd.DataFrame(columns=['ts','open','high','low','close','volume','oi']), source
    d = d.copy()
    d['ts'] = pd.to_datetime(d['ts'], utc=True, errors='coerce')
    for c in ['open','high','low','close','volume','oi']:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['ts','open','high','low','close']).sort_values('ts').reset_index(drop=True)
    return d, source
