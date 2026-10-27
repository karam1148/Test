"""Live Stock Tracker — run:  streamlit run app.py"""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tracker.data import INTERVALS, IST, fetch, normalize_symbol, nse_market_open
from tracker.signals import analyze, position_size, review_position

st.set_page_config(page_title="Live Stock Tracker", layout="wide")

COLORS = {"STRONG BUY": "#0a8f3c", "BUY": "#3cb371", "WAIT": "#9e9e9e", "SELL": "#e57373", "STRONG SELL": "#c62828"}

# ---------------- Sidebar ----------------
st.sidebar.title("⚙️ Settings")
exchange = st.sidebar.selectbox("Exchange", ["NSE", "BSE", "US"])
watch_raw = st.sidebar.text_area("Watchlist (comma separated)", "RELIANCE, TCS, HDFCBANK, INFY, SBIN")
interval = st.sidebar.selectbox("Timeframe", list(INTERVALS), index=2,
                                help="Intraday: 5m/15m, Swing: 1h/1d")
refresh = st.sidebar.slider("Auto refresh (seconds)", 15, 300, 60, step=15)
st.sidebar.markdown("---")
capital = st.sidebar.number_input("Trading capital (₹)", min_value=1000.0, value=100000.0, step=5000.0)
risk_pct = st.sidebar.slider("Risk per trade (% of capital)", 0.25, 3.0, 1.0, step=0.25)

symbols = [normalize_symbol(s, exchange) for s in watch_raw.split(",") if s.strip()]


@st.cache_data(ttl=10, show_spinner=False)
def load(sym: str, iv: str) -> pd.DataFrame:
    return fetch(sym, iv)


def fmt(x):
    return "—" if x is None else f"{x:,.2f}"


def chart(df: pd.DataFrame, sig, title: str) -> go.Figure:
    d = df.tail(150)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"), 1, 1)
    for col, color in [("EMA20", "#1e88e5"), ("EMA50", "#fb8c00"), ("EMA200", "#8e24aa")]:
        fig.add_trace(go.Scatter(x=d.index, y=d[col], name=col, line=dict(width=1.2, color=color)), 1, 1)
    up = d["ST"].where(d["ST_DIR"] > 0)
    dn = d["ST"].where(d["ST_DIR"] < 0)
    fig.add_trace(go.Scatter(x=d.index, y=up, name="SuperTrend ↑", line=dict(color="green", dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=d.index, y=dn, name="SuperTrend ↓", line=dict(color="red", dash="dot")), 1, 1)
    for lvl, name, color in [(sig.stop_loss, "Stop Loss", "red"), (sig.target1, "Target 1", "green"),
                             (sig.target2, "Target 2", "darkgreen"), (sig.entry, "Entry", "gray")]:
        if lvl is not None:
            fig.add_hline(y=lvl, line_dash="dash", line_color=color, annotation_text=f"{name} {lvl:,.2f}", row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d.RSI, name="RSI", line=dict(color="#6d4c41")), 2, 1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
    fig.add_trace(go.Bar(x=d.index, y=d.MACD_HIST, name="MACD hist",
                         marker_color=["green" if v >= 0 else "red" for v in d.MACD_HIST]), 3, 1)
    fig.update_layout(title=title, height=750, xaxis_rangeslider_visible=False, legend=dict(orientation="h"),
                      margin=dict(l=10, r=10, t=50, b=10))
    if interval != "1d":
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


@st.fragment(run_every=refresh)
def dashboard():
    now = datetime.now(IST)
    status = "🟢 NSE OPEN" if nse_market_open(now) else "🔴 NSE CLOSED"
    st.caption(f"Last update: {now:%d-%b-%Y %H:%M:%S} IST · {status} · auto-refresh every {refresh}s")

    rows, results = [], {}
    for sym in symbols:
        try:
            df, sig = analyze(load(sym, interval))
            results[sym] = (df, sig)
            chg = (sig.price / df["Close"].iloc[-2] - 1) * 100
            rows.append({"Symbol": sym, "Price": sig.price, "Chg % (bar)": chg, "Signal": sig.action,
                         "Score": sig.score, "RSI": sig.rsi, "Stop Loss": sig.stop_loss,
                         "Target 1": sig.target1, "Target 2": sig.target2})
        except Exception as e:  # one bad symbol shouldn't break the whole board
            rows.append({"Symbol": sym, "Signal": f"ERROR: {e}"})

    st.subheader("📋 Watchlist Scanner")
    table = pd.DataFrame(rows)
    st.dataframe(
        table.style.format(precision=2, na_rep="—").map(
            lambda v: f"color: white; background-color: {COLORS[v]}" if v in COLORS else "", subset=["Signal"]),
        width="stretch", hide_index=True,
    )

    if not results:
        st.warning("Koi valid symbol nahi mila.")
        return
    sym = st.selectbox("🔍 Detail view", list(results), key="detail_sym")
    df, sig = results[sym]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"<h2 style='color:{COLORS[sig.action]}'>{sig.action}</h2>", unsafe_allow_html=True)
    c2.metric("Price", fmt(sig.price))
    c3.metric("Stop Loss", fmt(sig.stop_loss))
    c4.metric("Target 1", fmt(sig.target1))
    c5.metric("Target 2", fmt(sig.target2))

    if sig.entry is not None:
        qty = position_size(capital, risk_pct, sig.entry, sig.stop_loss)
        side = "Buy" if "BUY" in sig.action else "Short-sell (intraday only)"
        st.info(f"**Plan:** {side} ~**{qty} shares** @ {fmt(sig.entry)} · SL {fmt(sig.stop_loss)} · "
                f"Max loss ≈ ₹{qty * abs(sig.entry - sig.stop_loss):,.0f} ({risk_pct}% of capital) · "
                f"Trailing SL (SuperTrend): {fmt(sig.trailing_sl)}  \n"
                f"Exit rule: Target 1 pe 50% book karo, SL entry pe shift karo; baaki Target 2 ya trailing SL tak.")
    else:
        st.warning("**WAIT** — trend clear nahi hai. Abhi naya trade mat lo.")
    for w in sig.warnings:
        st.error(w)

    st.plotly_chart(chart(df, sig, f"{sym} · {interval}"), width="stretch")

    with st.expander("Kyun ye signal? (indicator breakdown)"):
        st.write(f"Score: **{sig.score} / 6** · ATR: {sig.atr:,.2f} · RSI: {sig.rsi:.1f}")
        for r in sig.reasons:
            st.write("• " + r)

    st.subheader("💼 Meri Position check karo")
    p1, p2 = st.columns(2)
    buy_price = p1.number_input("Average buy price", min_value=0.0, value=0.0, key=f"bp_{sym}")
    qty_held = p2.number_input("Quantity", min_value=0, value=0, key=f"q_{sym}")
    if buy_price > 0 and qty_held > 0:
        r = review_position(df, sig, buy_price, qty_held)
        a, b, c, d = st.columns(4)
        a.metric("Advice", r["advice"])
        b.metric("P&L", f"₹{r['pnl']:,.0f}", f"{r['pnl_pct']:.2f}%")
        c.metric("Stop Loss (trail)", fmt(r["stop_loss"]))
        d.metric("Targets", f"{fmt(r['target1'])} / {fmt(r['target2'])}")
        st.write("➡️ " + r["why"])


st.title("📈 Live Stock Tracker — Buy / Sell / Stop-Loss")
st.caption("⚠️ Educational tool. Ye SEBI-registered advice nahi hai. Yahoo data thoda delayed ho sakta hai. "
           "Hamesha apna risk khud manage karo.")
dashboard()
