# 📈 Live Stock Tracker (Buy / Sell / Stop-Loss)

NSE / BSE / US stocks ki live tracking + automatic **Buy/Sell signal**, **Stop-Loss**, **Targets**, **Trailing SL** aur **position size**.

## Run kaise karein
```bash
pip install -r requirements.txt
streamlit run app.py
```
Browser mein `http://localhost:8501` khulega. Sidebar mein watchlist daalo (e.g. `RELIANCE, TCS, SBIN`), timeframe chuno — page apne aap refresh hota rahega.

## Kya milta hai
- **Watchlist scanner** — har stock ka signal (STRONG BUY / BUY / WAIT / SELL / STRONG SELL), SL, targets ek table mein
- **Chart** — Candles + EMA 20/50/200 + SuperTrend + RSI + MACD, SL/Target lines ke saath
- **Trade plan** — kitne shares lene hain taaki SL hit hone par sirf aapka chuna hua % (default 1%) capital jaaye
- **Meri Position** — apna buy price + qty daalo → HOLD / BOOK PARTIAL / BOOK PROFIT / EXIT advice + P&L

## Strategy logic (`tracker/signals.py`)
| Vote (+1 / −1) | Bullish jab |
|---|---|
| Price vs EMA20 | Price > EMA20 |
| EMA20 vs EMA50 | EMA20 > EMA50 |
| MACD histogram | > 0 |
| RSI | > 55 (bearish < 45) |
| SuperTrend (10, 3) | Uptrend |
| Price vs EMA200 | Price > EMA200 |

Score ≥ 4 STRONG BUY · ≥ 2 BUY · ≤ −2 SELL · ≤ −4 STRONG SELL · baaki WAIT

- **Stop-Loss** = Entry − 1.5 × ATR(14) (short ke liye +)
- **Target 1** = 1.5R, **Target 2** = 3R (R = entry − SL)
- **Exit rule:** T1 pe 50% book, SL ko entry (cost) pe le aao; baaki T2 ya SuperTrend trailing SL tak hold

## Timeframe guide
- Intraday: `5m` / `15m` · Swing (days–weeks): `1h` / `1d`

## Limitations (zaroor padhein)
- Data Yahoo Finance se aata hai — free hai lekin **kuch minute delayed** ho sakta hai. Tick-by-tick real-time ke liye broker API (Zerodha Kite Connect, Upstox, Angel SmartAPI) lagani padegi — `tracker/data.py` ka `fetch()` replace karna kaafi hai.
- Indicator-based signals sideways market mein galat (whipsaw) de sakte hain. Koi bhi strategy 100% accurate nahi hoti.
- Ye educational tool hai, SEBI-registered investment advice nahi. Pehle paper-trading karke test karein.

## Tests
```bash
pip install pytest && python -m pytest -q tests
```
