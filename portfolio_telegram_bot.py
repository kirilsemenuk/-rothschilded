import os
import io
import json
import math
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import yfinance as yf
import matplotlib.pyplot as plt


# =========================
# Environment Variables
# =========================
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# אפשר לשנות לשם קובץ אחר, למשל: holdings.json
PORTFOLIO_JSON = os.environ.get("PORTFOLIO_JSON", "portfolio.json")

# אופציונלי
TIMEZONE_NAME = os.environ.get("TIMEZONE_NAME", "Asia/Jerusalem")


# =========================
# Config
# =========================
CHIP_TICKERS = {"AMD", "NVDA", "INTC", "AMAT", "TSM", "AVGO", "MU", "QCOM"}
DAYS_HISTORY = 30


# =========================
# Helpers
# =========================
def format_currency(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


def format_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def get_dot_emoji(value: float) -> str:
    if value > 0:
        return "🟢"
    if value < 0:
        return "🔴"
    return "⚪️"


def get_status_text(daily_change: float) -> str:
    if daily_change > 0:
        return "יום חיובי"
    if daily_change < 0:
        return "יום שלילי"
    return "ללא שינוי"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


# =========================
# Portfolio
# =========================
def load_portfolio(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("portfolio.json must contain a list of holdings")

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
def fetch_prices_and_history(portfolio: List[dict], days: int = 30):
    """
    מחזיר:
    1. prices:
       {
         "AMD": {"price": 125.0, "prev_close": 120.0, "name": "Advanced Micro Devices, Inc."}
       }

    2. portfolio_history:
       list of {"date": datetime, "value": float}
    """
    tickers = [item["ticker"] for item in portfolio]
    prices: Dict[str, dict] = {}

    end_date = datetime.utcnow() + timedelta(days=1)
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
            fast_info = getattr(yf_ticker, "fast_info", None)
            if fast_info:
                pass
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
    """
    בונה היסטוריית שווי תיק לפי מחירי סגירה.
    """
    common_dates = None

    for item in portfolio:
        ticker = item["ticker"]
        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"].copy()
        hist = hist.dropna(subset=["Close"])
        hist.index = hist.index.tz_localize(None) if getattr(hist.index, "tz", None) else hist.index
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

            hist = prices[ticker]["hist"]
            hist = hist.dropna(subset=["Close"])
            hist.index = hist.index.tz_localize(None) if getattr(hist.index, "tz", None) else hist.index

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

    gainers = [x for x in snapshot if x["daily_pct"] > 0]
    losers = [x for x in snapshot if x["daily_pct"] < 0]
    unchanged = [x for x in snapshot if abs(x["daily_pct"]) < 1e-12]

    top_gainer = max(snapshot, key=lambda x: x["daily_pct"], default=None)
    top_impact = max(snapshot, key=lambda x: x["daily_pnl"], default=None)
    worst_impact = min(snapshot, key=lambda x: x["daily_pnl"], default=None)

    return {
        "portfolio_value": portfolio_value,
        "cost_basis": cost_basis,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_change": daily_change,
        "daily_change_pct": daily_change_pct,
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "unchanged_count": len(unchanged),
        "top_gainer": top_gainer,
        "top_impact": top_impact,
        "worst_impact": worst_impact,
        "top_gainers": sorted(gainers, key=lambda x: x["daily_pct"], reverse=True)[:3],
        "top_losers": sorted(losers, key=lambda x: x["daily_pct"])[:3],
    }


def build_daily_insight(metrics: dict) -> str:
    daily_change = metrics["daily_change"]
    top_impact = metrics["top_impact"]
    worst_impact = metrics["worst_impact"]
    top_gainers = metrics["top_gainers"]

    if not top_impact:
        return "לא זוהתה תנועה משמעותית בתיק היום."

    leading_tickers = {x["ticker"] for x in top_gainers}
    chip_names = sorted(list(leading_tickers.intersection(CHIP_TICKERS)))

    if daily_change > 0 and chip_names:
        return (
            f"סקטור השבבים הוביל את העליות היום ({', '.join(chip_names)}), "
            f"כש-{top_impact['ticker']} תרמה הכי הרבה לתיק."
        )

    if daily_change > 0:
        return f"{top_impact['ticker']} הובילה את התרומה היומית ודחפה את התיק ליום חיובי."

    if daily_change < 0 and worst_impact:
        return f"{worst_impact['ticker']} הייתה הגורם המרכזי ללחץ השלילי על התיק היום."

    return "התיק נסגר כמעט ללא שינוי, בלי מניה דומיננטית במיוחד."


def build_day_score(metrics: dict) -> float:
    score = 5.0

    score += min(max(metrics["daily_change_pct"] * 2.0, -3.0), 3.0)

    breadth = metrics["gainers_count"] - metrics["losers_count"]
    score += min(max(breadth * 0.25, -2.0), 2.0)

    if metrics["top_gainer"] and metrics["top_gainer"]["daily_pct"] >= 3:
        score += 0.7

    return round(min(max(score, 0.0), 10.0), 1)


# =========================
# Message Builders
# =========================
def build_daily_summary_message(metrics: dict, high_30d: Optional[float], low_30d: Optional[float]) -> str:
    status_emoji = get_dot_emoji(metrics["daily_change"])
    day_score = build_day_score(metrics)
    insight = build_daily_insight(metrics)

    winners_lines = [
        f"• {get_dot_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}"
        for item in metrics["top_gainers"]
    ] or ["• אין"]

    losers_lines = [
        f"• {get_dot_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}"
        for item in metrics["top_losers"]
    ] or ["• אין"]

    top_gainer_line = "—"
    if metrics["top_gainer"]:
        top_gainer_line = f"{metrics['top_gainer']['ticker']} {format_percent(metrics['top_gainer']['daily_pct'])}"

    top_impact_line = "—"
    if metrics["top_impact"]:
        top_impact_line = (
            f"{metrics['top_impact']['ticker']} "
            f"({format_currency(metrics['top_impact']['daily_pnl'])} לתיק)"
        )

    lines = [
        "📊 סיכום יומי – Rothschild",
        "",
        f"{status_emoji} מצב: {get_status_text(metrics['daily_change'])}",
        f"💰 שווי תיק: {format_currency(metrics['portfolio_value'])}",
        f"📈 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})",
        f"🟢 שינוי יומי: {format_currency(metrics['daily_change'])} ({format_percent(metrics['daily_change_pct'])})",
        f"🎯 ציון יום: {day_score}/10",
        "",
        "──────────────",
        "",
        f"🏆 כוכבת היום: {top_gainer_line}",
        f"💵 השפעה מובילה: {top_impact_line}",
        "",
        f"📊 רוחב שוק בתיק: {metrics['gainers_count']} עלו | {metrics['losers_count']} ירדו | {metrics['unchanged_count']} ללא שינוי",
        "",
        "🚀 מובילות היום:",
        *winners_lines,
        "",
        "📉 חלשות היום:",
        *losers_lines,
        "",
        f"🧠 תובנה: {insight}",
    ]

    if high_30d is not None or low_30d is not None:
        lines.extend([
            "",
            "📍 נקודות מפתח:",
            f"🔺 שיא 30 יום: {format_currency(high_30d) if high_30d is not None else '—'}",
            f"🔻 שפל 30 יום: {format_currency(low_30d) if low_30d is not None else '—'}",
        ])

    return "\n".join(lines)


def build_chart_caption(metrics: dict) -> str:
    return (
        "📈 גרף שווי תיק - 30 ימים אחרונים\n\n"
        f"💰 שווי נוכחי: {format_currency(metrics['portfolio_value'])}\n"
        f"📊 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})"
    )


# =========================
# Chart
# =========================
def create_portfolio_chart(history: List[dict], cost_basis: float, output_path: str = "portfolio_chart.png"):
    if not history:
        raise ValueError("No portfolio history to plot")

    dates = [item["date"] for item in history]
    values = [item["value"] for item in history]

    current_value = values[-1]
    current_profit = current_value - cost_basis
    current_profit_pct = (current_profit / cost_basis * 100) if cost_basis else 0.0

    high_value = max(values)
    low_value = min(values)
    high_idx = values.index(high_value)
    low_idx = values.index(low_value)

    plt.figure(figsize=(12, 6))
    plt.plot(dates, values, linewidth=2, label="Portfolio Value")
    plt.fill_between(dates, values, alpha=0.15)

    plt.axhline(cost_basis, linestyle="--", linewidth=1.2, label=f"Cost Basis (${cost_basis:,.0f})")

    plt.scatter(dates[high_idx], high_value, s=60, label="High")
    plt.scatter(dates[low_idx], low_value, s=60, label="Low")
    plt.scatter(dates[-1], values[-1], s=60, label="Today")

    plt.annotate(
        f"High\n${high_value:,.0f}",
        (dates[high_idx], high_value),
        textcoords="offset points",
        xytext=(0, 10),
        ha="center",
    )

    plt.annotate(
        f"Low\n${low_value:,.0f}",
        (dates[low_idx], low_value),
        textcoords="offset points",
        xytext=(0, -25),
        ha="center",
    )

    plt.annotate(
        f"Today\n${values[-1]:,.0f}",
        (dates[-1], values[-1]),
        textcoords="offset points",
        xytext=(0, 10),
        ha="center",
    )

    plt.title(
        f"Portfolio Value - Last 30 Days\n"
        f"Current Profit: ${current_profit:,.2f} ({current_profit_pct:.2f}%+)"
    )
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close()

    return output_path, high_value, low_value


# =========================
# Telegram
# =========================
def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": TG_CHAT_ID,
            "text": text,
        },
        timeout=30,
    )
    response.raise_for_status()


def send_telegram_photo(photo_path: str, caption: Optional[str] = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": TG_CHAT_ID}
        if caption:
            data["caption"] = caption

        response = requests.post(
            url,
            data=data,
            files=files,
            timeout=60,
        )
        response.raise_for_status()


def send_error_to_telegram(error_text: str):
    safe_text = f"❌ Portfolio bot error\n\n{error_text[:3500]}"
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

    print("Calculating snapshot...")
    snapshot = build_positions_snapshot(portfolio, prices)
    metrics = calculate_portfolio_metrics(snapshot)

    print("Building chart...")
    chart_path, high_30d, low_30d = create_portfolio_chart(
        history=history,
        cost_basis=metrics["cost_basis"],
        output_path="portfolio_chart.png",
    )

    print("Building messages...")
    daily_message = build_daily_summary_message(
        metrics=metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )

    chart_caption = build_chart_caption(metrics)

    print("Sending daily summary...")
    send_telegram_message(daily_message)

    print("Sending chart...")
    send_telegram_photo(chart_path, caption=chart_caption)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback_str = traceback.format_exc()
        print(traceback_str)
        send_error_to_telegram(traceback_str)
        raise
