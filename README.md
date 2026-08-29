# Nifty Vision

Nifty Vision is a Streamlit-based NIFTY 50 market-intelligence dashboard built around live market data from Upstox. It is designed to help a trader understand **what price is doing, where important levels are, which patterns are appearing, and what the options market is suggesting**.

> **Important:** Nifty Vision is an analytical tool, not a guarantee of future prices or trading profits. Signals are calculated from market data and should be treated as decision-support information, not financial advice.

## What Nifty Vision does

The application has two main analytical areas:

1. **NIFTY Vision** — price action, trend, technical indicators, support/resistance, market structure and candlestick patterns.
2. **Options Trading** — option-chain data, open interest, PCR, IV, Greeks, max pain, option support/resistance and options-market interpretation.

The dashboard refreshes automatically and is intended to make complex market information easier to read without requiring the user to calculate everything manually.

---

# 1. NIFTY PRICE ACTION

## Candles

Each candle represents a period of trading and contains four prices:

- **Open** — first traded price of the period.
- **High** — highest traded price.
- **Low** — lowest traded price.
- **Close** — last traded price.

A green candle means the close is above the open. A red candle means the close is below the open.

The dashboard supports multiple timeframes, including 1m, 3m, 5m, 15m, 30m, 1h and 1 day where the underlying data is available.

## Candle patterns

Nifty Vision identifies common price-action patterns from OHLC data. The pattern engine looks at the relationship between the current candle's open, high, low and close and, where required, compares it with nearby candles.

### Doji
A Doji has a very small real body compared with its trading range. It indicates that buyers and sellers finished the period close to balance.

### Bullish Engulfing
A bullish candle substantially covers the previous bearish candle's body. It can indicate a possible shift toward buyers, particularly after a decline.

### Bearish Engulfing
A bearish candle substantially covers the previous bullish candle's body. It can indicate a possible shift toward sellers, particularly after a rise.

### Hammer
A candle with a relatively small body and a long lower wick. It can show rejection of lower prices.

### Shooting Star
A candle with a relatively small body and a long upper wick. It can show rejection of higher prices.

**Important:** A pattern is not treated as a guaranteed reversal. Nifty Vision displays the detected pattern and its calculated direction/confidence so it can be considered together with trend and market structure.

---

# 2. MOVING AVERAGES

## EMA 9 / 20 / 50

Nifty Vision calculates exponential moving averages using the closing price.

An EMA gives more weight to recent prices than older prices. The basic recursive calculation is:

`EMA(today) = Price(today) × α + EMA(previous) × (1 − α)`

where:

`α = 2 / (period + 1)`

The dashboard uses periods of **9, 20 and 50**.

### How traders commonly read them

- Price above the EMA can indicate short-term strength.
- Price below the EMA can indicate short-term weakness.
- A faster EMA moving above a slower EMA can indicate improving momentum.
- A faster EMA moving below a slower EMA can indicate weakening momentum.

The dashboard does not assume that an EMA crossover alone is a trade signal.

---

# 3. VWAP

**VWAP = Volume Weighted Average Price.**

It answers a simple question:

> At what average price has the market traded, giving more importance to periods with greater volume?

For each period:

`Typical Price = (High + Low + Close) / 3`

Then:

`VWAP = Σ(Typical Price × Volume) / Σ(Volume)`

For intraday timeframes, Nifty Vision calculates VWAP using the trading session. For the daily view, the calculation is cumulative over the displayed daily data.

### Common interpretation

- Price above VWAP can indicate that buyers currently have an advantage relative to the volume-weighted average price.
- Price below VWAP can indicate seller advantage.
- VWAP can also act as a reference level during intraday trading.

---

# 4. RSI 14

**RSI (Relative Strength Index)** measures the speed and magnitude of recent price changes on a 0–100 scale.

Nifty Vision uses a 14-period RSI.

The calculation is based on average gains and average losses:

`RS = Average Gain / Average Loss`

`RSI = 100 − (100 / (1 + RS))`

### Common interpretation

- Around **70 or above** is traditionally considered overbought territory.
- Around **30 or below** is traditionally considered oversold territory.
- The area between them is not automatically bullish or bearish.

RSI is momentum information, not a prediction that price must reverse.

---

# 5. SUPPORT AND RESISTANCE

Nifty Vision calculates recent dynamic zones from the price series rather than manually entering fixed levels.

The engine looks at recent highs and lows and uses local rolling extrema to identify prices that have recently behaved like swing points.

A volatility measure based on the recent average high-low range is then used to turn the detected level into a **zone**, rather than pretending that support or resistance exists at one exact rupee value.

### Support
A recent area below the current price where buying/rejection has appeared.

### Resistance
A recent area above the current price where selling/rejection has appeared.

These are **calculated zones**, not guaranteed barriers.

---

# 6. MARKET STRUCTURE

Market structure tries to describe the sequence of swing highs and swing lows.

Nifty Vision uses structural labels such as:

- **HH — Higher High**
- **HL — Higher Low**
- **LH — Lower High**
- **LL — Lower Low**
- **BOS UP — Break of Structure upward**
- **BOS DOWN — Break of Structure downward**

### Simple interpretation

A sequence of higher highs and higher lows generally represents bullish structure.

A sequence of lower highs and lower lows generally represents bearish structure.

A **Break of Structure (BOS)** occurs when price breaks an important previously established structural point.

The dashboard combines the detected structural information into a market-regime view such as **BULLISH, BEARISH or NEUTRAL**.

---

# 7. SIGNAL SCORE

The dashboard combines price structure and detected patterns into a compact signal score.

The score is intended as a **summary of evidence**, not a probability of profit.

A trader should read the score together with:

- Current trend
- Market structure
- Support/resistance
- VWAP
- RSI
- Candle patterns
- Current price location

A high score does not mean a trade is guaranteed to work. It means more of the programmed conditions are pointing in the same direction.

---

# 8. OPTIONS TRADING

The options section uses the NIFTY option chain returned by Upstox.

For every strike, the application can work with:

- Call/Put LTP
- Open Interest
- Previous Open Interest
- Volume
- Implied Volatility
- Delta
- Gamma
- Theta
- Vega
- Bid/ask market data where available

The application first resolves the relevant NIFTY expiry and then builds a strike-wise dataset around the current ATM strike.

---

# 9. ATM STRIKE

**ATM = At The Money.**

Nifty Vision finds the strike whose strike price is closest to the current NIFTY spot price.

For example, if NIFTY is trading around 25,020 and available strikes are 24,900, 24,950, 25,000 and 25,050, the nearest strike is used as ATM.

The selected number of strikes around ATM can then be displayed for analysis.

---

# 10. PUT-CALL RATIO (PCR)

## PCR by Open Interest

`PCR = Total Put OI / Total Call OI`

Nifty Vision calculates this over the selected strike window.

A PCR above 1 means there is more Put OI than Call OI in that selected range. A PCR below 1 means the opposite.

PCR should **not** be interpreted as automatically bullish or bearish. Its meaning depends on price movement, OI changes, strike location and the wider market context.

## PCR by Volume

The dashboard can also calculate:

`Volume PCR = Total Put Volume / Total Call Volume`

This describes the relative amount of traded Put and Call volume in the selected strike window.

---

# 11. OPEN INTEREST (OI)

**Open Interest** represents outstanding option contracts that remain open.

Nifty Vision displays Call OI and Put OI by strike.

It also calculates the change from the previous OI value when the API supplies `prev_oi`:

`ΔOI = Current OI − Previous OI`

### Why OI matters

Large concentrations of Call OI can be areas where traders are positioned heavily on the Call side. Large concentrations of Put OI can similarly identify heavily positioned Put strikes.

These concentrations are used by the dashboard to estimate:

- **Put Support** — strongest Put OI concentration below spot.
- **Call Resistance** — strongest Call OI concentration above spot.

These are **OI-based reference levels**, not guaranteed support/resistance.

---

# 12. OI FLOW

Nifty Vision compares aggregated Call and Put ΔOI in the selected strike window.

If Call ΔOI is materially larger than Put ΔOI, the dashboard can classify the current flow as **CALL WRITING**.

If Put ΔOI is materially larger than Call ΔOI, it can classify the flow as **PUT WRITING**.

Otherwise it is shown as **BALANCED**.

The current classification is deliberately simple. It should not be confused with a complete four-way OI buildup model because that requires observing both **price change and OI change over time**.

---

# 13. IMPLIED VOLATILITY (IV)

**Implied Volatility** is the volatility level implied by an option's market price under an option-pricing model.

Nifty Vision reads IV supplied by the Upstox option-chain data rather than inventing its own IV number.

### ATM IV

The dashboard takes the Call IV and Put IV around the ATM strike and calculates their average when both are available:

`ATM IV = (Call IV + Put IV) / 2`

### IV Skew

The dashboard calculates:

`IV Skew = Put IV − Call IV`

A positive value means Put IV is higher than Call IV at ATM. A negative value means Call IV is higher.

**IV is not the same thing as direction.** Higher IV generally represents a higher option premium for a given set of other inputs, reflecting greater expected/required volatility and/or demand.

---

# 14. OPTION GREEKS

The Greeks describe how an option's theoretical value responds to changes in important variables.

## Delta

Delta estimates the change in option price for a small change in the underlying price, all else equal.

For example, a Call with delta near 0.50 is roughly sensitive to half the underlying's movement for a small move, subject to the model and changing conditions.

## Gamma

Gamma describes how quickly Delta changes as the underlying moves.

High Gamma means Delta can change rapidly, especially around ATM and near expiry.

## Theta

Theta represents the effect of time passing on an option's theoretical value, all else equal.

Option buyers are generally exposed to time decay, while option sellers generally benefit from it, though real-world P&L depends on the complete position and market movement.

## Vega

Vega measures sensitivity to changes in implied volatility.

An option with higher Vega is generally more sensitive to a change in IV.

Nifty Vision reads these Greek values from the option-chain response rather than calculating a separate theoretical model.

---

# 15. MAX PAIN

Max Pain is an estimate based on open interest showing the strike at which the combined intrinsic payout represented by outstanding Calls and Puts is lowest at expiry.

For every candidate settlement strike `S`, Nifty Vision calculates an aggregate payout using Call and Put OI:

`Call payout = Σ Call OI × max(S − Strike, 0)`

`Put payout = Σ Put OI × max(Strike − S, 0)`

The strike with the **lowest combined payout** is shown as Max Pain.

Max Pain is a market-derived reference, not a prediction that NIFTY will finish there.

---

# 16. OPTIONS MARKET REGIME

The Options Trading page combines several simple pieces of evidence into a compact regime label:

- PCR level
- OI flow classification
- Relative location of major Put/Call OI walls

The current scoring logic assigns directional points to these conditions and labels the result:

- **BULLISH** — stronger positive evidence.
- **BEARISH** — stronger negative evidence.
- **NEUTRAL** — evidence is mixed or insufficient.

This is a rule-based interpretation layer. It is **not machine learning, not a probability model and not a guarantee of direction**.

---

# 17. WHAT IS CALCULATED BY NIFTY VISION VS. WHAT COMES FROM UPSTOX?

## Calculated by Nifty Vision

- EMA 9 / 20 / 50
- VWAP
- RSI 14
- Recent support/resistance zones
- Market-structure labels
- Candlestick pattern detection
- Signal score
- ATM strike selection
- PCR
- Volume PCR
- ΔOI from current OI and previous OI
- OI-based Put Support / Call Resistance
- ATM IV average
- IV skew
- Max Pain
- Options market regime

## Supplied by Upstox

- NIFTY market data
- Option-chain strikes
- Call/Put LTP
- Open Interest and previous OI where available
- Volume
- Bid/ask data where available
- Implied Volatility
- Delta
- Gamma
- Theta
- Vega

This distinction is important: **Nifty Vision calculates the analytical layer, while Upstox supplies the underlying market observations and option-chain values.**

---

# 18. WHY THE DASHBOARD USES ZONES AND NOT EXACT LEVELS

Financial markets rarely respect one exact price to the rupee. A level can be tested several times over a range of prices.

For that reason, Nifty Vision uses a volatility-adjusted band around detected support and resistance points instead of presenting a single number as if it were exact.

The displayed zone should therefore be read as:

> **An area where price has recently shown relevant behaviour.**

---

# 19. OPTION CHARTS — PLANNED / IN DEVELOPMENT

The next major options upgrade is a true **historical option price-action chart**.

The planned design includes:

- CE / PE selection
- Expiry selection
- Strike selection
- Candlestick OHLC chart
- 1m / 3m / 5m / 15m / 30m / 1h / 1D timeframes where historical data is available
- Historical range controls
- Volume
- EMA
- VWAP
- RSI
- OI / ΔOI
- IV
- Greeks

This will allow the user to study an individual option contract as a price-action instrument rather than only viewing a current option-chain snapshot.

---

# 20. IMPORTANT LIMITATIONS

Nifty Vision should not be treated as an autonomous trading system.

- Market data can be delayed, incomplete or temporarily unavailable.
- API responses can change or contain missing fields.
- Technical indicators are derived from historical/current market observations and can produce false signals.
- OI concentration does not guarantee support or resistance.
- PCR does not independently predict market direction.
- Max Pain does not guarantee expiry settlement.
- Greeks change continuously as price, volatility and time change.
- The current OI-flow classification is not a complete position-identification model.
- Historical IV percentile/rank requires stored historical IV observations and is not inferred from a single snapshot.

Always verify important information against the live market before making a trading decision.

---

# Running the project

Add the Upstox token to Streamlit Secrets:

`UPSTOX_ACCESS_TOKEN = "your_token"`

Run locally with:

`streamlit run app.py`

The application uses Streamlit for the interface, Plotly for interactive charts and Upstox for market data.
