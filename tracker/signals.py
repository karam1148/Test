"""Buy/Sell signal engine with stop-loss, targets and position sizing.

Signal = sum of 6 trend/momentum votes (+1 bullish / -1 bearish):
  1. Close vs EMA20          4. RSI >55 / <45 (0 in between)
  2. EMA20 vs EMA50          5. SuperTrend direction
  3. MACD histogram sign     6. Close vs EMA200 (big trend)
Score >= 4 STRONG BUY, >= 2 BUY, <= -4 STRONG SELL, <= -2 SELL, else WAIT.

Risk levels (ATR based):
  Stop-loss  = entry -/+ 1.5 x ATR      (R = risk per share)
  Target 1   = entry +/- 1.5 R,  Target 2 = entry +/- 3 R
  Trailing SL = SuperTrend line (move SL up as trend runs)
"""
from dataclasses import dataclass, field
import math

import pandas as pd

from .indicators import add_all

SL_ATR = 1.5
T1_R = 1.5
T2_R = 3.0


@dataclass
class Signal:
    action: str
    score: int
    price: float
    entry: float | None = None
    stop_loss: float | None = None
    target1: float | None = None
    target2: float | None = None
    trailing_sl: float | None = None
    rsi: float = 0.0
    atr: float = 0.0
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _vote(cond_up: bool, cond_down: bool) -> int:
    return 1 if cond_up else (-1 if cond_down else 0)


def analyze(raw: pd.DataFrame) -> tuple[pd.DataFrame, Signal]:
    if len(raw) < 60:
        raise ValueError("Kam se kam 60 candles chahiye analysis ke liye")
    df = add_all(raw)
    last, prev = df.iloc[-1], df.iloc[-2]
    c = float(last["Close"])

    votes = {
        "Price vs EMA20": _vote(c > last["EMA20"], c < last["EMA20"]),
        "EMA20 vs EMA50": _vote(last["EMA20"] > last["EMA50"], last["EMA20"] < last["EMA50"]),
        "MACD histogram": _vote(last["MACD_HIST"] > 0, last["MACD_HIST"] < 0),
        "RSI momentum": _vote(last["RSI"] > 55, last["RSI"] < 45),
        "SuperTrend": int(last["ST_DIR"]),
        "Price vs EMA200": _vote(c > last["EMA200"], c < last["EMA200"]),
    }
    score = sum(votes.values())
    if score >= 4:
        action = "STRONG BUY"
    elif score >= 2:
        action = "BUY"
    elif score <= -4:
        action = "STRONG SELL"
    elif score <= -2:
        action = "SELL"
    else:
        action = "WAIT"

    a = float(last["ATR"])
    sig = Signal(action=action, score=score, price=c, rsi=float(last["RSI"]), atr=a)
    sig.reasons = [f"{k}: {'Bullish' if v > 0 else 'Bearish' if v < 0 else 'Neutral'}" for k, v in votes.items()]

    # Fresh crossover events on the latest candle
    if prev["EMA20"] <= prev["EMA50"] and last["EMA20"] > last["EMA50"]:
        sig.reasons.append("Fresh EMA20/50 bullish crossover")
    if prev["EMA20"] >= prev["EMA50"] and last["EMA20"] < last["EMA50"]:
        sig.reasons.append("Fresh EMA20/50 bearish crossover")
    if prev["ST_DIR"] != last["ST_DIR"]:
        sig.reasons.append(f"SuperTrend just flipped {'UP' if last['ST_DIR'] > 0 else 'DOWN'}")

    if sig.rsi > 75:
        sig.warnings.append("RSI overbought (>75): naya buy chase mat karo, pullback ka wait karo")
    if sig.rsi < 25:
        sig.warnings.append("RSI oversold (<25): naya short risky hai, bounce aa sakta hai")

    if "BUY" in action:
        risk = SL_ATR * a
        sig.entry, sig.stop_loss = c, c - risk
        sig.target1, sig.target2 = c + T1_R * risk, c + T2_R * risk
        sig.trailing_sl = float(last["ST"]) if last["ST_DIR"] > 0 else None
    elif "SELL" in action:
        risk = SL_ATR * a
        sig.entry, sig.stop_loss = c, c + risk
        sig.target1, sig.target2 = c - T1_R * risk, c - T2_R * risk
        sig.trailing_sl = float(last["ST"]) if last["ST_DIR"] < 0 else None
    return df, sig


def position_size(capital: float, risk_pct: float, entry: float, stop: float) -> int:
    """Shares to buy so that hitting the stop-loss loses only risk_pct of capital."""
    per_share = abs(entry - stop)
    if per_share <= 0 or entry <= 0:
        return 0
    by_risk = math.floor(capital * risk_pct / 100 / per_share)
    by_cash = math.floor(capital / entry)
    return max(0, min(by_risk, by_cash))


def review_position(df: pd.DataFrame, sig: Signal, buy_price: float, qty: int) -> dict:
    """Advice for an existing LONG holding: HOLD / BOOK PARTIAL / EXIT."""
    last = df.iloc[-1]
    c = sig.price
    a = sig.atr
    initial_sl = buy_price - SL_ATR * a
    trail = float(last["ST"]) if last["ST_DIR"] > 0 else None
    stop = max(initial_sl, trail) if trail is not None else initial_sl
    risk = SL_ATR * a
    t1, t2 = buy_price + T1_R * risk, buy_price + T2_R * risk
    pnl = (c - buy_price) * qty

    if c <= stop:
        advice, why = "EXIT", "Price stop-loss / trailing SL ke neeche hai"
    elif sig.score <= -2:
        advice, why = "EXIT", "Trend bearish ho gaya (signal SELL)"
    elif c >= t2:
        advice, why = "BOOK PROFIT", "Target 2 hit; zyada maal becho, baaki trailing SL ke saath"
    elif c >= t1 or sig.rsi > 75:
        advice, why = "BOOK PARTIAL", "Target 1 hit / RSI overbought; 30-50% book karo, SL cost pe le aao"
    else:
        advice, why = "HOLD", "Trend intact; SL ke upar hai"
    return {
        "advice": advice, "why": why, "stop_loss": stop, "target1": t1, "target2": t2,
        "pnl": pnl, "pnl_pct": (c / buy_price - 1) * 100 if buy_price else 0.0,
    }
