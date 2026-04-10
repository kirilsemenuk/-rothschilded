import os
import io
import json
import math
import requests
import datetime as dt
from typing import List, Dict, Tuple

import yfinance as yf
import matplotlib.pyplot as plt


TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
PORTFOLIO_FILE = os.environ.get("PORTFOLIO_FILE", "portfolio.json")


def fmt_money(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}${x:,.2f}"


def fmt_pct(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        },
        timeout=30,
    )
    resp.raise_for_status()


def send_telegram_photo(photo_bytes: bytes, caption: str = "") -> None:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("portfolio.png", photo_bytes, "image/png")}
    data = {
        "chat_id": TG_CHAT_ID,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()

def load_portfolio(file_path: str) -> List[Dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_tickers(portfolio: List[Dict]) -> List[str]:
    return sorted({item["ticker"].upper() for item in portfolio})


def safe_float(value, default=0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except Exception:
        return default


def download_market_data(tickers: List[str], period: str = "1mo", interval: str = "1d"):
    data = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    return data


def get_last_two_closes(data, ticker: str) -> Tuple[float, float]:
    try:
        series = data[ticker]["Close"].dropna()
    except Exception:
        series = data["Close"][ticker].dropna()

    if len(series) == 0:
        return 0.0, 0.0
    if len(series) == 1:
        close = safe_float(series.iloc[-1])
        return close, close

    last_close = safe_float(series.iloc[-1])
    prev_close = safe_float(series.iloc[-2])
    return last_close, prev_close


def get_portfolio_timeseries(data, portfolio: List[Dict]) -> List[Tuple[dt.date, float]]:
    totals_by_date = {}

    for item in portfolio:
        ticker = item["ticker"].upper()
        shares = safe_float(item["shares"])

        try:
            closes = data[ticker]["Close"].dropna()
        except Exception:
            closes = data["Close"][ticker].dropna()

        for idx, price in closes.items():
            day = idx.date() if hasattr(idx, "date") else idx
            totals_by_date.setdefault(day, 0.0)
            totals_by_date[day] += shares * safe_float(price)

    return sorted(totals_by_date.items(), key=lambda x: x[0])


def analyze_portfolio(portfolio: List[Dict], data) -> Dict:
    holdings = []
    total_value = 0.0
    total_cost = 0.0
    daily_change_value = 0.0

    for item in portfolio:
        ticker = item["ticker"].upper()
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        last_close, prev_close = get_last_two_closes(data, ticker)

        market_value = shares * last_close
        cost_basis = shares * avg_price
        profit = market_value - cost_basis
        profit_pct = (profit / cost_basis * 100) if cost_basis else 0.0

        daily_change_stock = shares * (last_close - prev_close)
        daily_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else 0.0

        holdings.append(
            {
                "ticker": ticker,
                "shares": shares,
                "avg_price": avg_price,
                "last_close": last_close,
                "prev_close": prev_close,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "profit": profit,
                "profit_pct": profit_pct,
                "daily_change_value": daily_change_stock,
                "daily_pct": daily_pct,
            }
        )

        total_value += market_value
        total_cost += cost_basis
        daily_change_value += daily_change_stock

    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost else 0.0

    top_gainers = sorted(holdings, key=lambda x: x["daily_pct"], reverse=True)[:3]
    top_losers = sorted(holdings, key=lambda x: x["daily_pct"])[:3]

    return {
        "holdings": holdings,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_change_value": daily_change_value,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


def build_daily_summary(report: Dict) -> str:
    daily_change = report["daily_change_value"]
    emoji = "🟢" if daily_change >= 0 else "🔴"

    lines = [
        "📅 *סיכום יומי*",
        "",
        f"{emoji} שינוי יומי בתיק: {fmt_money(daily_change)}",
    ]

    if report["top_gainers"]:
        gainers = ", ".join(
            [f'{x["ticker"]} ({fmt_pct(x["daily_pct"])})' for x in report["top_gainers"]]
        )
        lines.append(f"🚀 מניות בולטות: {gainers}")

    if daily_change >= 0:
        lines.append("🧠 התיק סגר את היום בעלייה, עם תרומה חיובית מהמניות המובילות.")
    else:
        lines.append("🧠 התיק סגר את היום בירידה, בעיקר בגלל החולשה במניות החלשות.")

    return "\n".join(lines)


def build_portfolio_summary(report: Dict) -> str:
    daily_change = report["daily_change_value"]
    daily_emoji = "🟢" if daily_change >= 0 else "🔴"

    lines = [
        "📊 *סיכום פיננסי*",
        "",
        f'💰 *שווי תיק:* {fmt_money(report["total_value"]).replace("+", "")}',
        f'📈 *רווח כולל:* {fmt_money(report["total_profit"])} ({fmt_pct(report["total_profit_pct"])})',
        f"{daily_emoji} *שינוי יומי:* {fmt_money(daily_change)}",
        "",
        "🚀 *מובילות היום:*",
    ]

    for item in report["top_gainers"]:
        icon = "🟢" if item["daily_pct"] >= 0 else "🔴"
        lines.append(f'• {icon} {item["ticker"]} {fmt_pct(item["daily_pct"])}')

    lines.append("")
    lines.append("📉 *חלשות היום:*")
    for item in report["top_losers"]:
        icon = "🟢" if item["daily_pct"] >= 0 else "🔴"
        lines.append(f'• {icon} {item["ticker"]} {fmt_pct(item["daily_pct"])}')

    gainers_names = ", ".join([x["ticker"] for x in report["top_gainers"]])
    losers_names = ", ".join([x["ticker"] for x in report["top_losers"]])

    lines.extend(
        [
            "",
            "🧠 *תובנה:*",
            f"עיקר התנועה בתיק היום הגיע מ-{gainers_names}, בעוד שהחולשה העיקרית נרשמה ב-{losers_names}.",
        ]
    )

    return "\n".join(lines)


def build_chart(report: Dict, data, portfolio: List[Dict]) -> bytes:
    timeseries = get_portfolio_timeseries(data, portfolio)
    dates = [x[0] for x in timeseries]
    values = [x[1] for x in timeseries]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, linewidth=2)
    plt.title("Portfolio Value - Last 1 Month")
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    max_idx = values.index(max(values))
    min_idx = values.index(min(values))
    plt.scatter([dates[max_idx]], [values[max_idx]], s=60)
    plt.scatter([dates[min_idx]], [values[min_idx]], s=60)
    plt.annotate("High", (dates[max_idx], values[max_idx]), textcoords="offset points", xytext=(0, 8), ha="center")
    plt.annotate("Low", (dates[min_idx], values[min_idx]), textcoords="offset points", xytext=(0, -15), ha="center")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160)
    plt.close()
    buf.seek(0)
    return buf.read()


def main():
    portfolio = load_portfolio(PORTFOLIO_FILE)
    tickers = get_tickers(portfolio)
    data = download_market_data(tickers, period="1mo", interval="1d")
    report = analyze_portfolio(portfolio, data)

    daily_summary = build_daily_summary(report)
    portfolio_summary = build_portfolio_summary(report)
    chart = build_chart(report, data, portfolio)

    send_telegram_message(daily_summary)
    send_telegram_photo(chart, caption="📈 גרף שווי תיק - חודש אחרון")
    send_telegram_message(portfolio_summary)


if __name__ == "__main__":
    main()
