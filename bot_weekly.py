import os
import json
import math
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
import yfinance as yf
import matplotlib.pyplot as plt


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
PORTFOLIO_JSON = os.environ.get("PORTFOLIO_JSON", "portfolio.json")

CHIP_TICKERS = {"AMD", "NVDA", "INTC", "AMAT", "TSM", "AVGO", "MU", "QCOM"}
DAYS_HISTORY = 30
BENCHMARK_TICKER = "VOO"


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


def format_score(score: float) -> str:
    return str(int(score)) if float(score).is_integer() else f"{score:.1f}"


def get_dot_emoji(value: float) -> str:
    if value > 0:
        return "🟢"
    if value < 0:
        return "🔴"
    return "⚪️"


def get_week_status_text(weekly_change: float) -> str:
    if weekly_change > 0:
        return "שבוע חיובי"
    if weekly_change < 0:
        return "שבוע שלילי"
    return "ללא שינוי"


def get_trend_text(weekly_change_pct: float) -> str:
    if weekly_change_pct > 3:
        return "🚀 מגמה: Strong Uptrend"
    if weekly_change_pct > 1:
        return "📈 מגמה: Uptrend"
    if weekly_change_pct > -1:
        return "➖ מגמה: Sideways"
    return "📉 מגמה: Downtrend"


def load_portfolio(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("portfolio json must contain a list")

    portfolio = []
    for item in data:
        ticker = str(item["ticker"]).upper().strip()
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        if not ticker or shares <= 0:
            continue

        portfolio.append({
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
        })

    if not portfolio:
        raise ValueError("portfolio is empty")

    return portfolio


def fetch_ticker_history(ticker: str, period: str = "3mo"):
    hist = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if hist.empty:
        return hist

    hist = hist.dropna(subset=["Close"]).copy()
    if getattr(hist.index, "tz", None) is not None:
        hist.index = hist.index.tz_localize(None)
    return hist


def fetch_prices_and_history(portfolio: List[dict], days: int = 30):
    prices: Dict[str, dict] = {}

    for item in portfolio:
        ticker = item["ticker"]
        print(f"Fetching {ticker}...")

        hist = fetch_ticker_history(ticker, period="3mo")
        if hist.empty:
            print(f"Warning: no data for {ticker}")
            continue

        current_price = safe_float(hist["Close"].iloc[-1])
        prev_close = current_price
        week_ago_close = current_price

        if len(hist) >= 2:
            prev_close = safe_float(hist["Close"].iloc[-2], current_price)

        if len(hist) >= 6:
            week_ago_close = safe_float(hist["Close"].iloc[-6], current_price)
        else:
            week_ago_close = safe_float(hist["Close"].iloc[0], current_price)

        prices[ticker] = {
            "price": current_price,
            "prev_close": prev_close,
            "week_ago_close": week_ago_close,
            "hist": hist.tail(max(days, 10)),
        }

    if not prices:
        raise RuntimeError("failed to fetch prices")

    history = build_portfolio_history(portfolio, prices, days=days)
    return prices, history


def build_portfolio_history(portfolio: List[dict], prices: Dict[str, dict], days: int = 30) -> List[dict]:
    common_dates = None

    for item in portfolio:
        ticker = item["ticker"]
        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"]
        ticker_dates = set(d.date() for d in hist.index)

        if common_dates is None:
            common_dates = ticker_dates
        else:
            common_dates = common_dates.intersection(ticker_dates)

    if not common_dates:
        return []

    common_dates = sorted(common_dates)[-days:]
    history = []

    for date_only in common_dates:
        total_value = 0.0

        for item in portfolio:
            ticker = item["ticker"]
            shares = item["shares"]

            if ticker not in prices:
                continue

            hist = prices[ticker]["hist"]
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
        week_ago_close = safe_float(prices[ticker]["week_ago_close"], current_price)

        market_value = shares * current_price
        cost_basis = shares * avg_price

        total_profit = market_value - cost_basis
        total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

        daily_pnl = shares * (current_price - prev_close)
        daily_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        weekly_pnl = shares * (current_price - week_ago_close)
        weekly_pct = ((current_price - week_ago_close) / week_ago_close * 100) if week_ago_close else 0.0

        snapshot.append({
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
            "current_price": current_price,
            "prev_close": prev_close,
            "week_ago_close": week_ago_close,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "daily_pnl": daily_pnl,
            "daily_pct": daily_pct,
            "weekly_pnl": weekly_pnl,
            "weekly_pct": weekly_pct,
        })

    if not snapshot:
        raise RuntimeError("no valid positions after fetch")

    return snapshot


def build_weekly_score(metrics: dict) -> float:
    score = 5.0
    score += min(max(metrics["weekly_change_pct"] * 0.8, -3.0), 3.0)

    breadth = metrics["weekly_gainers_count"] - metrics["weekly_losers_count"]
    score += min(max(breadth * 0.2, -2.0), 2.0)

    if metrics.get("top_weekly_gainer") and metrics["top_weekly_gainer"]["weekly_pct"] >= 8:
        score += 0.8

    return round(min(max(score, 0.0), 10.0), 1)


def calculate_weekly_metrics(snapshot: List[dict], benchmark_pct: Optional[float] = None) -> dict:
    portfolio_value = sum(x["market_value"] for x in snapshot)
    cost_basis = sum(x["cost_basis"] for x in snapshot)
    total_profit = portfolio_value - cost_basis
    total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

    weekly_change = sum(x["weekly_pnl"] for x in snapshot)
    prev_week_value = sum(x["shares"] * x["week_ago_close"] for x in snapshot)
    weekly_change_pct = (weekly_change / prev_week_value * 100) if prev_week_value else 0.0

    weekly_gainers = [x for x in snapshot if x["weekly_pct"] > 0]
    weekly_losers = [x for x in snapshot if x["weekly_pct"] < 0]
    weekly_unchanged = [x for x in snapshot if abs(x["weekly_pct"]) < 1e-12]

    top_weekly_gainer = max(snapshot, key=lambda x: x["weekly_pct"], default=None)
    top_weekly_impact = max(snapshot, key=lambda x: x["weekly_pnl"], default=None)

    metrics = {
        "portfolio_value": portfolio_value,
        "cost_basis": cost_basis,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "weekly_change": weekly_change,
        "weekly_change_pct": weekly_change_pct,
        "weekly_gainers_count": len(weekly_gainers),
        "weekly_losers_count": len(weekly_losers),
        "weekly_unchanged_count": len(weekly_unchanged),
        "top_weekly_gainer": top_weekly_gainer,
        "top_weekly_impact": top_weekly_impact,
        "top_weekly_gainers": sorted(weekly_gainers, key=lambda x: x["weekly_pct"], reverse=True)[:3],
        "top_weekly_losers": sorted(weekly_losers, key=lambda x: x["weekly_pct"])[:3],
        "benchmark_name": BENCHMARK_TICKER if benchmark_pct is not None else None,
        "benchmark_pct": benchmark_pct,
    }

    metrics["weekly_score"] = build_weekly_score(metrics)
    return metrics


def build_weekly_insight(metrics: dict) -> str:
    weekly_change_pct = metrics["weekly_change_pct"]
    top_weekly_impact = metrics.get("top_weekly_impact")
    top_weekly_gainers = metrics.get("top_weekly_gainers", [])

    if not top_weekly_impact:
        return "🧠 סיכום: השבוע נסגר ללא מניה דומיננטית במיוחד."

    leading_tickers = {x["ticker"] for x in top_weekly_gainers}
    chip_names = sorted(list(leading_tickers.intersection(CHIP_TICKERS)))

    if weekly_change_pct > 0 and chip_names:
        return (
            f"🧠 סיכום: שבוע חזק לתיק עם הובלה של מניות השבבים "
            f"({', '.join(chip_names)}) ותרומה מרכזית מ-{top_weekly_impact['ticker']}."
        )

    if weekly_change_pct > 0:
        return f"🧠 סיכום: שבוע חיובי לתיק, עם תרומה מרכזית מ-{top_weekly_impact['ticker']}."

    if weekly_change_pct < 0:
        return f"🧠 סיכום: שבוע חלש יותר לתיק, כשההשפעה המרכזית הגיעה מ-{top_weekly_impact['ticker']}."

    return "🧠 סיכום: השבוע נסגר כמעט ללא שינוי."


def build_weekly_summary_message(metrics: dict, high_30d: Optional[float], low_30d: Optional[float]) -> str:
    score_str = format_score(metrics["weekly_score"])
    trend_line = get_trend_text(metrics["weekly_change_pct"])
    insight = build_weekly_insight(metrics)

    top_impact_line = "—"
    if metrics.get("top_weekly_impact"):
        top_impact_line = (
            f"{metrics['top_weekly_impact']['ticker']} "
            f"{format_currency(metrics['top_weekly_impact']['weekly_pnl'])}"
        )

    market_block = []
    if metrics.get("benchmark_name") and metrics.get("benchmark_pct") is not None:
        market_block = [
            f"📊 מול השוק ({metrics['benchmark_name']}):",
            f"אתה: {format_percent(metrics['weekly_change_pct'])}",
            f"השוק: {format_percent(metrics['benchmark_pct'])}",
            f"יתרון: {format_percent(metrics['weekly_change_pct'] - metrics['benchmark_pct'])}",
            "",
        ]

    winners_lines = [
        f"• {get_dot_emoji(item['weekly_pct'])} {item['ticker']} {format_percent(item['weekly_pct'])}"
        for item in metrics["top_weekly_gainers"]
    ] or ["• אין"]

    losers_lines = [
        f"• {get_dot_emoji(item['weekly_pct'])} {item['ticker']} {format_percent(item['weekly_pct'])}"
        for item in metrics["top_weekly_losers"]
    ] or ["• אין"]

    lines = [
        "📅 Rothschild – סיכום שבועי",
        "",
        trend_line,
        f"{get_dot_emoji(metrics['weekly_change'])} מצב: {get_week_status_text(metrics['weekly_change'])}",
        f"💰 שווי תיק: {format_currency_plain(metrics['portfolio_value'])}",
        f"📈 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})",
        f"🗓️ שינוי שבועי: {format_currency(metrics['weekly_change'])} ({format_percent(metrics['weekly_change_pct'])})",
        f"🎯 ציון שבוע: {score_str}/10",
        "",
        *market_block,
        "──────────────",
        "",
        "💵 התרומה הגדולה ביותר:",
        top_impact_line,
        "",
        f"📊 רוחב שוק בתיק: {metrics['weekly_gainers_count']} עלו | {metrics['weekly_losers_count']} ירדו | {metrics['weekly_unchanged_count']} ללא שינוי",
        "",
        "🚀 מובילות השבוע:",
        *winners_lines,
        "",
        "📉 חלשות השבוע:",
        *losers_lines,
        "",
        insight,
    ]

    if high_30d is not None or low_30d is not None:
        lines.extend([
            "",
            "📍 טווח 30 יום:",
            f"🔺 שיא: {format_currency_plain(high_30d) if high_30d is not None else '—'}",
            f"🔻 שפל: {format_currency_plain(low_30d) if low_30d is not None else '—'}",
        ])

    return "\n".join(lines)


def build_chart_caption(metrics: dict) -> str:
    return "📈 גרף שווי תיק - 30 ימים אחרונים"


def create_portfolio_chart(history: List[dict], cost_basis: float, output_path: str = "portfolio_weekly_chart.png"):
    if not history:
        raise ValueError("no portfolio history to plot")

    dates = [item["date"] for item in history]
    values = [item["value"] for item in history]

    high_value = max(values)
    low_value = min(values)
    high_idx = values.index(high_value)
    low_idx = values.index(low_value)
    today_value = values[-1]

    plt.figure(figsize=(12, 6))
    plt.plot(dates, values, linewidth=2, label="Portfolio Value")
    plt.fill_between(dates, values, alpha=0.15)
    plt.axhline(cost_basis, linestyle="--", linewidth=1.2, label="Cost Basis")

    plt.scatter(dates[high_idx], high_value, s=60, label="High")
    plt.scatter(dates[low_idx], low_value, s=60, label="Low")
    plt.scatter(dates[-1], today_value, s=60, label="Today")

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
        f"Today\n${today_value:,.0f}",
        (dates[-1], today_value),
        textcoords="offset points",
        xytext=(0, 10),
        ha="center",
    )

    plt.title("Portfolio Value - Last 30 Days")
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close()

    return output_path, high_value, low_value


def fetch_benchmark_weekly_pct(ticker: str = BENCHMARK_TICKER) -> Optional[float]:
    hist = fetch_ticker_history(ticker, period="10d")
    if hist.empty:
        return None

    current_price = safe_float(hist["Close"].iloc[-1])
    if len(hist) >= 6:
        week_ago_close = safe_float(hist["Close"].iloc[-6], current_price)
    else:
        week_ago_close = safe_float(hist["Close"].iloc[0], current_price)

    if not week_ago_close:
        return None

    return ((current_price - week_ago_close) / week_ago_close) * 100


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
    try:
        send_telegram_message(f"❌ bot_weekly.py error\n\n{error_text[:3500]}")
    except Exception:
        print("failed to send error to telegram")


def main():
    print("Loading portfolio...")
    portfolio = load_portfolio(PORTFOLIO_JSON)

    print("Fetching prices...")
    prices, history = fetch_prices_and_history(portfolio, days=DAYS_HISTORY)
    print(f"Fetched data for {len(prices)} tickers.")

    print("Building snapshot...")
    snapshot = build_positions_snapshot(portfolio, prices)

    print("Fetching benchmark...")
    benchmark_pct = fetch_benchmark_weekly_pct(BENCHMARK_TICKER)

    print("Calculating weekly metrics...")
    weekly_metrics = calculate_weekly_metrics(snapshot, benchmark_pct=benchmark_pct)

    print("Creating chart...")
    chart_path, high_30d, low_30d = create_portfolio_chart(
        history=history,
        cost_basis=weekly_metrics["cost_basis"],
        output_path="portfolio_weekly_chart.png",
    )

    print("Building message...")
    weekly_message = build_weekly_summary_message(
        metrics=weekly_metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )
    chart_caption = build_chart_caption(weekly_metrics)

    print("Sending weekly summary...")
    send_telegram_message(weekly_message)

    print("Sending chart...")
    send_telegram_photo(chart_path, caption=chart_caption)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        print(error_text)
        send_error_to_telegram(error_text)
        raise
