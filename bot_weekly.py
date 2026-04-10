import os
import json
import math
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# =========================
# Environment Variables
# =========================
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
PORTFOLIO_JSON = os.environ.get("PORTFOLIO_JSON", "portfolio.json")
BENCHMARK_TICKER = os.environ.get("BENCHMARK_TICKER", "VOO")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


# =========================
# Config
# =========================
CHIP_TICKERS = {"AMD", "NVDA", "INTC", "AMAT", "TSM", "AVGO", "MU", "QCOM"}
DAYS_HISTORY = 30
REQUEST_TIMEOUT = 45


# =========================
# Helpers
# =========================
def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default



def format_currency(value: float) -> str:
    if value > 0:
        return f"+${abs(value):,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${abs(value):,.2f}"



def format_currency_plain(value: float) -> str:
    return f"${abs(value):,.2f}"



def format_percent(value: float) -> str:
    if value > 0:
        return f"+{value:.2f}%"
    if value < 0:
        return f"{value:.2f}%"
    return f"{value:.2f}%"



def get_dot_emoji(value: float) -> str:
    if value > 0:
        return "🟢"
    if value < 0:
        return "🔴"
    return "⚪️"



def trim_text(text: str, max_len: int = 800) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


# =========================
# Portfolio
# =========================
def load_portfolio(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("portfolio file must contain a list of holdings")

    normalized = []
    for item in data:
        ticker = str(item["ticker"]).upper().strip()
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        if not ticker or shares <= 0:
            continue

        normalized.append({
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
        })

    if not normalized:
        raise ValueError("Portfolio is empty or invalid")

    return normalized


# =========================
# Market Data
# =========================
def fetch_single_ticker_history(ticker: str, days: int = 30):
    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=max(days * 3, 60))

    yf_ticker = yf.Ticker(ticker)
    hist = yf_ticker.history(start=start_date, end=end_date, auto_adjust=False)
    hist = hist.dropna(subset=["Close"])

    if hist.empty:
        raise RuntimeError(f"No market data for {ticker}")

    info_name = ticker
    try:
        info = yf_ticker.info
        info_name = info.get("shortName") or info.get("longName") or ticker
    except Exception:
        pass

    return {
        "ticker": ticker,
        "name": info_name,
        "hist": hist.tail(days),
        "price": safe_float(hist["Close"].iloc[-1]),
        "prev_close": safe_float(hist["Close"].iloc[-2] if len(hist) >= 2 else hist["Close"].iloc[-1]),
    }



def fetch_prices_and_history(portfolio: List[dict], days: int = 30):
    tickers = [item["ticker"] for item in portfolio]
    prices: Dict[str, dict] = {}

    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=max(days * 3, 60))

    for ticker in tickers:
        print(f"Fetching {ticker}...")
        yf_ticker = yf.Ticker(ticker)

        hist = yf_ticker.history(start=start_date, end=end_date, auto_adjust=False)
        if hist.empty:
            print(f"Warning: no data for {ticker}")
            continue

        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            print(f"Warning: empty close data for {ticker}")
            continue

        current_price = safe_float(hist["Close"].iloc[-1])
        prev_close = current_price
        if len(hist) >= 2:
            prev_close = safe_float(hist["Close"].iloc[-2], current_price)

        info_name = ticker
        try:
            info = yf_ticker.info
            info_name = info.get("shortName") or info.get("longName") or ticker
        except Exception:
            info_name = ticker

        prices[ticker] = {
            "price": current_price,
            "prev_close": prev_close,
            "name": info_name,
            "hist": hist.tail(days),
        }

    if not prices:
        raise RuntimeError("Failed to fetch any market data")

    portfolio_history = build_portfolio_history(portfolio, prices, days=days)
    return prices, portfolio_history



def build_portfolio_history(portfolio: List[dict], prices: Dict[str, dict], days: int = 30):
    common_dates = None

    for item in portfolio:
        ticker = item["ticker"]
        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"].copy()
        hist = hist.dropna(subset=["Close"])
        if getattr(hist.index, "tz", None) is not None:
            hist.index = hist.index.tz_localize(None)

        ticker_dates = set(d.date() for d in hist.index)

        if common_dates is None:
            common_dates = ticker_dates
        else:
            common_dates = common_dates.intersection(ticker_dates)

    if not common_dates:
        return []

    common_dates = sorted(list(common_dates))[-days:]
    history = []

    for date_only in common_dates:
        total_value = 0.0

        for item in portfolio:
            ticker = item["ticker"]
            shares = item["shares"]

            if ticker not in prices:
                continue

            hist = prices[ticker]["hist"].copy()
            hist = hist.dropna(subset=["Close"])
            if getattr(hist.index, "tz", None) is not None:
                hist.index = hist.index.tz_localize(None)

            same_day = hist[hist.index.date == date_only]
            if same_day.empty:
                continue

            close_price = safe_float(same_day["Close"].iloc[-1])
            total_value += shares * close_price

        history.append({
            "date": datetime.combine(date_only, datetime.min.time()),
            "value": total_value,
        })

    return history


# =========================
# Calculations
# =========================
def build_positions_snapshot(portfolio: List[dict], prices: Dict[str, dict]) -> List[dict]:
    snapshot = []

    for item in portfolio:
        ticker = item["ticker"]
        shares = item["shares"]
        avg_price = item["avg_price"]

        if ticker not in prices:
            continue

        current_price = safe_float(prices[ticker]["price"])
        prev_close = safe_float(prices[ticker]["prev_close"], current_price)

        market_value = shares * current_price
        cost_basis = shares * avg_price
        total_profit = market_value - cost_basis
        total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

        daily_pnl = shares * (current_price - prev_close)
        daily_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        snapshot.append({
            "ticker": ticker,
            "name": prices[ticker].get("name", ticker),
            "shares": shares,
            "avg_price": avg_price,
            "current_price": current_price,
            "prev_close": prev_close,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "daily_pnl": daily_pnl,
            "daily_pct": daily_pct,
        })

    if not snapshot:
        raise RuntimeError("No valid positions after price fetch")

    return snapshot



def calculate_portfolio_metrics(snapshot: List[dict]) -> dict:
    portfolio_value = sum(x["market_value"] for x in snapshot)
    cost_basis = sum(x["cost_basis"] for x in snapshot)
    total_profit = portfolio_value - cost_basis
    total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

    daily_change = sum(x["daily_pnl"] for x in snapshot)
    prev_value = sum(x["shares"] * x["prev_close"] for x in snapshot)
    daily_change_pct = (daily_change / prev_value * 100) if prev_value else 0.0

    return {
        "portfolio_value": portfolio_value,
        "cost_basis": cost_basis,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_change": daily_change,
        "daily_change_pct": daily_change_pct,
    }



def calculate_weekly_change_from_history(history: List[dict]) -> Tuple[float, float]:
    if not history or len(history) < 2:
        return 0.0, 0.0

    end_value = history[-1]["value"]
    start_idx = max(0, len(history) - 6)
    start_value = history[start_idx]["value"]

    weekly_change = end_value - start_value
    weekly_change_pct = (weekly_change / start_value * 100) if start_value else 0.0
    return weekly_change, weekly_change_pct



def build_weekly_positions_snapshot(portfolio: List[dict], prices: Dict[str, dict]) -> List[dict]:
    snapshot = []

    for item in portfolio:
        ticker = item["ticker"]
        shares = item["shares"]
        avg_price = item["avg_price"]

        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"].dropna(subset=["Close"]).copy()
        if hist.empty:
            continue

        current_price = safe_float(hist["Close"].iloc[-1])
        start_idx = max(0, len(hist) - 6)
        week_start_price = safe_float(hist["Close"].iloc[start_idx], current_price)

        market_value = shares * current_price
        cost_basis = shares * avg_price
        total_profit = market_value - cost_basis
        total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

        weekly_pnl = shares * (current_price - week_start_price)
        weekly_pct = ((current_price - week_start_price) / week_start_price * 100) if week_start_price else 0.0

        snapshot.append({
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
            "current_price": current_price,
            "week_start_price": week_start_price,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "weekly_pnl": weekly_pnl,
            "weekly_pct": weekly_pct,
        })

    return snapshot



def calculate_weekly_metrics(snapshot: List[dict], history: List[dict]) -> dict:
    weekly_change, weekly_change_pct = calculate_weekly_change_from_history(history)

    gainers = [x for x in snapshot if x["weekly_pct"] > 0]
    losers = [x for x in snapshot if x["weekly_pct"] < 0]
    unchanged = [x for x in snapshot if abs(x["weekly_pct"]) < 1e-12]

    top_gainer = max(snapshot, key=lambda x: x["weekly_pct"], default=None)
    top_impact = max(snapshot, key=lambda x: x["weekly_pnl"], default=None)
    worst_impact = min(snapshot, key=lambda x: x["weekly_pnl"], default=None)

    return {
        "weekly_change": weekly_change,
        "weekly_change_pct": weekly_change_pct,
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "unchanged_count": len(unchanged),
        "top_gainer": top_gainer,
        "top_impact": top_impact,
        "worst_impact": worst_impact,
        "top_gainers": sorted(gainers, key=lambda x: x["weekly_pct"], reverse=True)[:3],
        "top_losers": sorted(losers, key=lambda x: x["weekly_pct"])[:3],
    }


# =========================
# Benchmark / Market
# =========================
def calculate_benchmark_comparison(history: List[dict], benchmark_ticker: str) -> dict:
    result = {
        "ticker": benchmark_ticker,
        "weekly_pct": 0.0,
        "weekly_delta_vs_market": 0.0,
        "weekly_text": "אין נתונים",
    }

    if not history or len(history) < 2:
        return result

    try:
        benchmark = fetch_single_ticker_history(benchmark_ticker, days=30)
        hist = benchmark["hist"].dropna(subset=["Close"]).copy()
        if hist.empty:
            return result

        _, portfolio_weekly_pct = calculate_weekly_change_from_history(history)

        benchmark_today = safe_float(hist["Close"].iloc[-1])
        week_start_idx = max(0, len(hist) - 6)
        benchmark_week_start = safe_float(hist["Close"].iloc[week_start_idx], benchmark_today)
        benchmark_weekly_pct = ((benchmark_today - benchmark_week_start) / benchmark_week_start * 100) if benchmark_week_start else 0.0

        weekly_delta = portfolio_weekly_pct - benchmark_weekly_pct

        result.update({
            "ticker": benchmark_ticker,
            "weekly_pct": benchmark_weekly_pct,
            "weekly_delta_vs_market": weekly_delta,
            "weekly_text": (
                f"ניצחת את {benchmark_ticker} השבוע"
                if weekly_delta > 0 else
                f"היית מתחת ל-{benchmark_ticker} השבוע"
                if weekly_delta < 0 else
                f"היית בקו אחד עם {benchmark_ticker} השבוע"
            ),
            "portfolio_weekly_pct": portfolio_weekly_pct,
        })
        return result
    except Exception as e:
        print(f"Benchmark comparison failed: {e}")
        return result


# =========================
# Scoring + Insights
# =========================
def build_week_score(weekly_metrics: dict) -> float:
    score = 5.0
    score += min(max(weekly_metrics["weekly_change_pct"] * 1.5, -3.0), 3.0)

    breadth = weekly_metrics["gainers_count"] - weekly_metrics["losers_count"]
    score += min(max(breadth * 0.30, -2.0), 2.0)

    if weekly_metrics.get("top_gainer") and weekly_metrics["top_gainer"]["weekly_pct"] >= 5:
        score += 0.8

    return round(min(max(score, 0.0), 10.0), 1)



def build_weekly_insight(weekly_metrics: dict) -> str:
    weekly_change = weekly_metrics["weekly_change"]
    top_impact = weekly_metrics.get("top_impact")
    worst_impact = weekly_metrics.get("worst_impact")
    top_gainers = weekly_metrics.get("top_gainers", [])

    if not top_impact:
        return "לא זוהתה תנועה שבועית משמעותית."

    leading_tickers = {x["ticker"] for x in top_gainers}
    chip_names = sorted(list(leading_tickers.intersection(CHIP_TICKERS)))

    if weekly_change > 0 and chip_names:
        return f"מניות השבבים בלטו גם השבוע, כש-{top_impact['ticker']} תרמה הכי הרבה לתיק."

    if weekly_change > 0:
        return f"{top_impact['ticker']} הייתה המניה המשפיעה ביותר השבוע וסייעה לדחוף את התיק למעלה."

    if weekly_change < 0 and worst_impact:
        return f"{worst_impact['ticker']} הייתה הגורם המרכזי ללחץ השלילי על התיק השבוע."

    return "התיק סיים את השבוע כמעט ללא שינוי."


# =========================
# GROQ Insight
# =========================
def build_groq_prompt(metrics: dict, weekly_metrics: dict, benchmark: dict) -> str:
    return f"""
אתה אנליסט תיקי השקעות. כתוב תובנה שבועית אחת בעברית, במשפט עד שניים, בסגנון חד וטבעי.
בלי אזהרות, בלי דיסקליימרים, בלי רשימות, בלי כותרת.

נתונים:
- שינוי שבועי בתיק: {weekly_metrics['weekly_change']:.2f} דולר ({weekly_metrics['weekly_change_pct']:.2f}%)
- רווח כולל: {metrics['total_profit']:.2f} דולר ({metrics['total_profit_pct']:.2f}%)
- הכי השפיעה השבוע: {weekly_metrics['top_impact']['ticker'] if weekly_metrics.get('top_impact') else 'N/A'}
- מובילות השבוע: {", ".join([f"{x['ticker']} {x['weekly_pct']:.2f}%" for x in weekly_metrics.get('top_gainers', [])])}
- חלשות השבוע: {", ".join([f"{x['ticker']} {x['weekly_pct']:.2f}%" for x in weekly_metrics.get('top_losers', [])])}
- מול השוק ({benchmark['ticker']}): התיק {benchmark.get('portfolio_weekly_pct', 0.0):.2f}%, השוק {benchmark.get('weekly_pct', 0.0):.2f}%, פער {benchmark.get('weekly_delta_vs_market', 0.0):.2f}%
    """.strip()



def generate_groq_insight(metrics: dict, weekly_metrics: dict, benchmark: dict) -> Optional[str]:
    if not GROQ_API_KEY:
        return None

    prompt = build_groq_prompt(metrics, weekly_metrics, benchmark)
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "ענה בעברית. כתוב קצר, חד, טבעי ומקצועי."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 120,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        return trim_text(text, 260)
    except Exception as e:
        print(f"GROQ insight failed: {e}")
        return None


# =========================
# Message Builders
# =========================
def build_vs_market_line(benchmark: dict) -> str:
    portfolio_pct = benchmark.get("portfolio_weekly_pct", 0.0)
    market_pct = benchmark.get("weekly_pct", 0.0)
    delta = benchmark.get("weekly_delta_vs_market", 0.0)
    return (
        f"📊 אני מול השוק ({benchmark['ticker']}): "
        f"אני {format_percent(portfolio_pct)} | "
        f"השוק {format_percent(market_pct)} | "
        f"פער {format_percent(delta)}"
    )



def build_weekly_summary_message(
    metrics: dict,
    weekly_metrics: dict,
    high_30d: Optional[float],
    low_30d: Optional[float],
    benchmark: dict,
    groq_insight: Optional[str] = None,
) -> str:
    status_emoji = get_dot_emoji(weekly_metrics["weekly_change"])
    week_score = build_week_score(weekly_metrics)
    insight = groq_insight or build_weekly_insight(weekly_metrics)

    winners_lines = [
        f"• {get_dot_emoji(item['weekly_pct'])} {item['ticker']} {format_percent(item['weekly_pct'])}"
        for item in weekly_metrics["top_gainers"]
    ] or ["• אין"]

    losers_lines = [
        f"• {get_dot_emoji(item['weekly_pct'])} {item['ticker']} {format_percent(item['weekly_pct'])}"
        for item in weekly_metrics["top_losers"]
    ] or ["• אין"]

    top_impact_line = "—"
    if weekly_metrics.get("top_impact"):
        top_impact_line = f"{weekly_metrics['top_impact']['ticker']} {format_currency(weekly_metrics['top_impact']['weekly_pnl'])}"

    status_text = "שבוע חיובי" if weekly_metrics["weekly_change"] > 0 else "שבוע שלילי" if weekly_metrics["weekly_change"] < 0 else "ללא שינוי"

    lines = [
        "📅 סיכום שבועי – Rothschild",
        "",
        f"{status_emoji} מצב: {status_text}",
        f"💰 שווי תיק: {format_currency_plain(metrics['portfolio_value'])}",
        f"📈 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})",
        f"🗓️ שינוי שבועי: {format_currency(weekly_metrics['weekly_change'])} ({format_percent(weekly_metrics['weekly_change_pct'])})",
        f"🎯 ציון שבוע: {week_score}/10",
        "",
        build_vs_market_line(benchmark),
        "",
        "──────────────",
        "",
        f"💵 הכי השפיעה השבוע: {top_impact_line}",
        "",
        f"📊 רוחב שוק בתיק: {weekly_metrics['gainers_count']} עלו | {weekly_metrics['losers_count']} ירדו | {weekly_metrics['unchanged_count']} ללא שינוי",
        "",
        "🚀 מובילות השבוע:",
        *winners_lines,
        "",
        "📉 חלשות השבוע:",
        *losers_lines,
        "",
        f"🧠 תובנה שבועית: {insight}",
    ]

    if high_30d is not None or low_30d is not None:
        lines.extend([
            "",
            "📍 שיא ושפל (30 יום):",
            f"🔺 שיא: {format_currency_plain(high_30d) if high_30d is not None else '—'}",
            f"🔻 שפל: {format_currency_plain(low_30d) if low_30d is not None else '—'}",
        ])

    return "\n".join(lines)



def build_weekly_chart_caption() -> str:
    return "📊 גרף ביצועי תיק - שבוע אחרון"


# =========================
# Premium Weekly Chart
# =========================
def create_weekly_portfolio_chart(
    history: List[dict],
    cost_basis: float,
    output_path: str = "portfolio_weekly_chart.png",
):
    if not history:
        raise ValueError("No portfolio history to plot")

    weekly_history = history[-7:] if len(history) >= 7 else history

    dates = [item["date"] for item in weekly_history]
    values = [item["value"] for item in weekly_history]

    high_value = max(values)
    low_value = min(values)
    today_value = values[-1]

    high_idx = values.index(high_value)
    low_idx = values.index(low_value)
    today_idx = len(values) - 1

    current_profit = today_value - cost_basis
    current_profit_pct = (current_profit / cost_basis * 100) if cost_basis else 0.0

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12.5, 6.8), dpi=170)

    fig.patch.set_facecolor("#0f1117")
    ax.set_facecolor("#171b26")

    ax.plot(dates, values, linewidth=2.8, color="#8b5cf6", label="Portfolio Value", zorder=3)
    ax.fill_between(dates, values, min(values) * 0.98, color="#8b5cf6", alpha=0.14, zorder=1)

    ax.axhline(
        cost_basis,
        linestyle="--",
        linewidth=1.4,
        color="#9aa4b2",
        alpha=0.9,
        label=f"Cost Basis (${cost_basis:,.0f})",
        zorder=2,
    )

    ax.scatter(dates[high_idx], high_value, s=85, color="#22c55e", edgecolors="white", linewidth=0.8, zorder=5)
    ax.scatter(dates[low_idx], low_value, s=85, color="#ef4444", edgecolors="white", linewidth=0.8, zorder=5)
    ax.scatter(dates[today_idx], today_value, s=95, color="#f59e0b", edgecolors="white", linewidth=0.9, zorder=6)

    ax.annotate(
        f"HIGH\n${high_value:,.0f}",
        (dates[high_idx], high_value),
        textcoords="offset points",
        xytext=(0, 14),
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#22c55e",
        bbox=dict(boxstyle="round,pad=0.25", fc="#0f1117", ec="#22c55e", alpha=0.85),
    )
    ax.annotate(
        f"LOW\n${low_value:,.0f}",
        (dates[low_idx], low_value),
        textcoords="offset points",
        xytext=(0, -34),
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#ef4444",
        bbox=dict(boxstyle="round,pad=0.25", fc="#0f1117", ec="#ef4444", alpha=0.85),
    )
    ax.annotate(
        f"TODAY\n${today_value:,.0f}",
        (dates[today_idx], today_value),
        textcoords="offset points",
        xytext=(0, 14),
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#f59e0b",
        bbox=dict(boxstyle="round,pad=0.25", fc="#0f1117", ec="#f59e0b", alpha=0.85),
    )

    ax.set_title(
        "Portfolio Value • Last Week\n"
        f"Current Profit: {'+' if current_profit > 0 else ''}${current_profit:,.2f} "
        f"({'+' if current_profit_pct > 0 else ''}{current_profit_pct:.2f}%)",
        fontsize=15,
        fontweight="bold",
        pad=18,
        color="white",
    )

    ax.set_xlabel("Date", fontsize=10, color="#cbd5e1", labelpad=10)
    ax.set_ylabel("Value ($)", fontsize=10, color="#cbd5e1", labelpad=10)
    ax.tick_params(axis="x", colors="#cbd5e1", labelsize=9)
    ax.tick_params(axis="y", colors="#cbd5e1", labelsize=9)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.18)

    for spine in ax.spines.values():
        spine.set_color("#2a3242")
        spine.set_linewidth(1.0)

    legend = ax.legend(
        loc="upper left",
        frameon=True,
        fancybox=True,
        framealpha=0.18,
        facecolor="#0f1117",
        edgecolor="#334155",
        fontsize=9,
    )
    for text in legend.get_texts():
        text.set_color("#e5e7eb")

    y_min = min(min(values), cost_basis) * 0.96
    y_max = max(max(values), cost_basis) * 1.04
    ax.set_ylim(y_min, y_max)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    return output_path, high_value, low_value


# =========================
# Telegram
# =========================
def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": TG_CHAT_ID, "text": text},
        timeout=30,
    )
    response.raise_for_status()



def send_telegram_photo(photo_path: str, caption: Optional[str] = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        response = requests.post(
            url,
            data={"chat_id": TG_CHAT_ID, "caption": caption or ""},
            files={"photo": f},
            timeout=60,
        )
        response.raise_for_status()



def send_error_to_telegram(error_text: str):
    safe_text = f"❌ Weekly portfolio bot error\n\n{trim_text(error_text, 3500)}"
    try:
        send_telegram_message(safe_text)
    except Exception:
        print("Failed sending error to Telegram")


# =========================
# Main
# =========================
def main():
    print("Loading portfolio...")
    portfolio = load_portfolio(PORTFOLIO_JSON)

    print("Fetching market data...")
    prices, history = fetch_prices_and_history(portfolio, days=DAYS_HISTORY)
    print(f"Fetched data for {len(prices)} tickers.")

    print("Calculating snapshots...")
    snapshot = build_positions_snapshot(portfolio, prices)
    metrics = calculate_portfolio_metrics(snapshot)

    weekly_snapshot = build_weekly_positions_snapshot(portfolio, prices)
    weekly_metrics = calculate_weekly_metrics(weekly_snapshot, history)

    print("Calculating benchmark comparison...")
    benchmark = calculate_benchmark_comparison(history, BENCHMARK_TICKER)

    print("Generating GROQ insight...")
    groq_weekly = generate_groq_insight(metrics, weekly_metrics, benchmark)

    print("Building weekly chart...")
    chart_path, high_30d, low_30d = create_weekly_portfolio_chart(
        history=history,
        cost_basis=metrics["cost_basis"],
        output_path="portfolio_weekly_chart.png",
    )

    print("Building weekly message...")
    weekly_message = build_weekly_summary_message(
        metrics=metrics,
        weekly_metrics=weekly_metrics,
        high_30d=high_30d,
        low_30d=low_30d,
        benchmark=benchmark,
        groq_insight=groq_weekly,
    )

    print("Sending weekly chart...")
    send_telegram_photo(chart_path, caption=build_weekly_chart_caption())

    print("Sending weekly summary...")
    send_telegram_message(weekly_message)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback_str = traceback.format_exc()
        print(traceback_str)
        send_error_to_telegram(traceback_str)
        raise
