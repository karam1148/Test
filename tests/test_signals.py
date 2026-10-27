import numpy as np
import pandas as pd

from tracker.signals import analyze, position_size, review_position


def make(trend: float, n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(trend / 100 + rng.normal(0, 0.005, n)))
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1000}, index=idx)


def test_uptrend_gives_buy_with_levels():
    _, s = analyze(make(0.5))
    assert "BUY" in s.action
    assert s.stop_loss < s.entry < s.target1 < s.target2


def test_downtrend_gives_sell_with_levels():
    _, s = analyze(make(-0.5))
    assert "SELL" in s.action
    assert s.stop_loss > s.entry > s.target1 > s.target2


def test_position_size_limits_risk():
    assert position_size(100000, 1, 100, 98) == 500     # 1000 risk / 2 per share
    assert position_size(10000, 5, 100, 99.9) == 100    # capped by cash


def test_review_exit_when_below_stop():
    df, s = analyze(make(-0.5))
    r = review_position(df, s, buy_price=s.price * 1.5, qty=10)
    assert r["advice"] == "EXIT" and r["pnl"] < 0
