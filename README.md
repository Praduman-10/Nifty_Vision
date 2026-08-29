# Nifty Vision

Live NIFTY 50 charting and price-action dashboard built with Streamlit and Upstox.

## Current build
- Live NIFTY 50 intraday candles
- 1m, 3m, 5m, 15m, 30m and 1h timeframes
- EMA 9 / 20 / 50
- VWAP and RSI 14
- Automatic recent support/resistance levels
- Doji, bullish/bearish engulfing, hammer and shooting-star detection
- Visual pattern annotations on the chart
- Automatic 30-second refresh

## Streamlit Secrets
Add `UPSTOX_ACCESS_TOKEN = "your_token"` to Streamlit Secrets.

## Run
`streamlit run app.py`

The next phase will add the dedicated NIFTY options screen, selected strikes, option-chain analytics, and a stronger multi-signal interpretation engine.
