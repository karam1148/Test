"""Market data via Yahoo Finance (yfinance). NSE = .NS, BSE = .BO suffix."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")

# interval -> lookback period (Yahoo limits: 1m <= 7d, intraday <= 60d)
INTERVALS = {
    "1m": "5d",
    "5m": "1mo",
    "15m": "60d",
    "1h": "6mo",
    "1d": "2y",
}


def normalize_symbol(sym: str, exchange: str = "NSE") -> str:
    sym = sym.strip().upper()
    if not sym or sym.startswith("^") or "." in sym or exchange == "US":
        return sym
    return sym + (".NS" if exchange == "NSE" else ".BO")


def fetch(symbol: str, interval: str = "15m") -> pd.DataFrame:
    df = yf.Ticker(symbol).history(period=INTERVALS[interval], interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError(f"{symbol}: data nahi mila (symbol galat ho sakta hai)")
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def nse_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(IST)
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)
