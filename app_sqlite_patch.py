"""SQLite-first integration helpers for the main Nifty Vision app.

Import these helpers from app.py when switching the dashboard's data source.
"""
from data_service import get_market_data, TIMEFRAMES


def load_for_dashboard(frame_label, candles=500):
    """Return stored historical candles, refreshing only the missing tail from Upstox."""
    if frame_label not in TIMEFRAMES:
        raise ValueError(f'Unsupported timeframe: {frame_label}')
    return get_market_data(frame_label, limit=candles)
