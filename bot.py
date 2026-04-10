import io
import json
import math
import os
import time
from typing import Dict, List, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
PORTFOLIO_FILE = os.environ.get("PORTFOLIO_FILE", "portfolio.json")


def require_env() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN")
    if not TG_CHAT_ID:
        raise ValueError("Missing TG_CHAT_ID")


def fmt_money(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}${x:,.2f}"


def fmt_pct(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        v = float(value)
        if math.isnan(v):
            return default
        return v
    except Exception:
        return default


def escape_markdown(text: str) -> str:
    special_chars = r"_*[]()~`>#+-=|{}.!\\"
    result = str(text)
    for ch in special_chars:
        result = result.replace(ch, f"\\{ch}")
    return result


def load_portfolio(file_path: str) -> List[Dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        portfolio = json.load(f)

    if not isinstance(portfolio, list):
        raise ValueError("portfolio.json must contain a list")

    cleaned = []
    for item in portfolio:
        ticker = str(item["ticker"]).upper().strip()
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        if not ticker:
            continue

        cleaned.append(
            {
                "ticker": ticker,
                "shares": shares,
                "avg_price": avg_price,
            }
        )

    if not cleaned:
        raise ValueError("Portfolio is empty")

    return cleaned


def get_tickers(portfolio: List[Dict]) -> List[str]:
    return sorted({item["ticker"] for item in portfolio})


def fetch_ticker_history(
    ticker: str,
    period: str = "1mo",
    interval: str = "1d",
    max_retries: int = 4,
    sleep_seconds: float = 3.0,
):
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            df = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )

            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    if "Close" in df.columns.get_level_values(0):
                        close_df = df["Close"].copy()
                        if isinstance(close_df, pd.Series):
                            close_df = close_df.to_frame(name=ticker)
                        else:
                            if len(close_df.columns) == 1:
                                close_df.columns = [ticker]
                        close_df = close_df.dropna(how="all")
                        if not close_df.empty:
                            return close_df

                if "Close" in df.columns:
                    close_series = df["Close"].dropna()
                    if not close_series.empty:
                        return close_series.to_frame(name=ticker)

            last_error = ValueError(f"No usable data returned for {ticker}")

        except Exception as e:
            last_error = e

        if attempt < max_retries:
            time.sleep(sleep_seconds * attempt)

    print(f"WARNING: failed to fetch {ticker}: {last_error}")
    return None


def download_market_data(
    tickers: List[str],
    period: str = "1mo",
    interval: str = "1d",
):
    frames = []
    failed = []

    for ticker in tickers:
        print(f"Fetching {ticker}...")
        frame = fetch_ticker_history(
            ticker=ticker,
            period=period,
            interval=interval,
            max_retries=4,
            sleep_seconds=3.0,
        )

        if frame is None or frame.empty:
            failed.append(ticker)
        else:
            frames.append(frame)

        time.sleep(1.5)

    if not frames:
        raise ValueError(
            f"No market data returned from yfinance. Failed tickers: {', '.join(failed)}"
        )

    combined = pd.concat(frames, axis=1).sort_index()
    combined = combined.dropna(how="all")

    print(f"Fetched data for {len(combined.columns)} tickers.")
    if failed:
        print(f"Failed tickers: {failed}")

    return combined, failed


def get_close_series(data, ticker: str):
    if ticker not in data.columns:
        raise KeyError(f"{ticker} not found in downloaded data")
    return data[ticker].dropna()


def get_last_two_closes(data, ticker: str) -> Tuple[float, float]:
    closes = get_close_series(data, ticker)

    if len(closes) == 0:
        return 0.0, 0.0
    if len(closes) == 1:
        close = safe_float(closes.iloc[-1])
        return close, close

    last_close = safe_float(closes.iloc[-1])
    prev_close = safe_float(closes.iloc[-2])
    return last_close, prev_close


def get_portfolio_timeseries(data, portfolio: List[Dict]) -> List[Tuple]:
    totals_by_date: Dict = {}

    for item in portfolio:
        ticker = item["ticker"]
        shares = safe_float(item["shares"])

        if ticker not in data.columns:
            continue

        closes = get_close_series(data, ticker)

        for idx, price in closes.items():
            day = idx.to_pydatetime()
            totals_by_date.setdefault(day, 0.0)
            totals_by_date[day] += shares * safe_float(price)

    return sorted(totals_by_date.items(), key=lambda x: x[0])


def analyze_portfolio(portfolio: List[Dict], data, failed_tickers: List[str]) -> Dict:
    holdings = []
    total_value = 0.0
    total_cost = 0.0
    daily_change_value = 0.0
    skipped = []

    for item in portfolio:
        ticker = item["ticker"]
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        if ticker not in data.columns:
            skipped.append(ticker)
            continue

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

    if not holdings:
        raise ValueError("No holdings could be analyzed from the downloaded data")

    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost else 0.0

    previous_total_value = total_value - daily_change_value
    daily_pct_total = (daily_change_value / previous_total_value * 100) if previous_total_value else 0.0

    top_gainers = sorted(holdings, key=lambda x: x["daily_pct"], reverse=True)[:3]
    top_losers = sorted(holdings, key=lambda x: x["daily_pct"])[:3]

    up_count = sum(1 for x in holdings if x["daily_pct"] > 0)
    down_count = sum(1 for x in holdings if x["daily_pct"] < 0)
    flat_count = sum(1 for x in holdings if x["daily_pct"] == 0)

    return {
        "holdings": holdings,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_change_value": daily_change_value,
        "daily_pct_total": daily_pct_total,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "failed_tickers": failed_tickers,
        "skipped_tickers": skipped,
    }


def get_market_status(daily_change: float) -> str:
    if daily_change > 50:
        return "🚀 יום חזק מאוד"
    if daily_change > 0:
        return "🟢 יום חיובי"
    if daily_change > -50:
        return "🟠 יום חלש"
    return "🔴 יום שלילי"


def build_insight(report: Dict) -> str:
    gainers = report["top_gainers"]
    losers = report["top_losers"]

    if gainers and gainers[0]["daily_pct"] > 2:
        return f"הובלה חזקה של {gainers[0]['ticker']} דחפה את התיק למעלה."
    if losers and losers[0]["daily_pct"] < -2:
        return f"חולשה ב-{losers[0]['ticker']} הפעילה לחץ על התיק."
    if report["daily_change_value"] > 0:
        return "התיק התקדם היום בצורה חיובית וללא תנודה חריגה."
    if report["daily_change_value"] < 0:
        return "התיק נחלש מעט היום, אך ללא שינוי קיצוני."
    return "היום נרשמה יציבות יחסית בתיק."


def build_daily_summary(report: Dict) -> str:
    daily_change = report["daily_change_value"]
    daily_pct_total = report["daily_pct_total"]
    status = get_market_status(daily_change)

    lines = [
        "📅 *סיכום יומי*",
        "",
        f"📊 מצב התיק: {escape_markdown(status)}",
        f"{'🟢' if daily_change >= 0 else '🔴'} שינוי יומי בתיק: {escape_markdown(fmt_money(daily_change))} ({escape_markdown(fmt_pct(daily_pct_total))})",
    ]

    if report["top_gainers"]:
        gainers = ", ".join(
            f"{x['ticker']} ({fmt_pct(x['daily_pct'])})"
            for x in report["top_gainers"]
        )
        lines.append(f"🚀 מניות בולטות: {escape_markdown(gainers)}")

    if report["failed_tickers"]:
        failed_text = ", ".join(report["failed_tickers"])
        lines.append(f"⚠️ לא עודכנו בגלל חסימת Yahoo: {escape_markdown(failed_text)}")

    lines.append(f"🧠 {escape_markdown(build_insight(report))}")
    return "\n".join(lines)


def build_portfolio_summary(report: Dict) -> str:
    daily_change = report["daily_change_value"]
    daily_pct_total = report["daily_pct_total"]
    status = get_market_status(daily_change)
    top_star = report["top_gainers"][0] if report["top_gainers"] else None

    portfolio_value_text = f"${report['total_value']:,.2f}"
    total_profit_text = fmt_money(report["total_profit"])
    total_profit_pct_text = fmt_pct(report["total_profit_pct"])
    daily_change_text = fmt_money(daily_change)
    daily_pct_text = fmt_pct(daily_pct_total)

    lines = [
        "📊 *סיכום פיננסי*",
        "",
        f"📌 מצב: {escape_markdown(status)}",
        f"💰 *שווי תיק:* {escape_markdown(portfolio_value_text)}",
        f"📈 *רווח כולל:* {escape_markdown(total_profit_text)} ({escape_markdown(total_profit_pct_text)})",
        f"{'🟢' if daily_change >= 0 else '🔴'} *שינוי יומי:* {escape_markdown(daily_change_text)} ({escape_markdown(daily_pct_text)})",
        "",
    ]

    if top_star:
        lines.append(
            f"🏆 *כוכבת היום:* {escape_markdown(top_star['ticker'])} {escape_markdown(fmt_pct(top_star['daily_pct']))}"
        )
        lines.append("")

    lines.append(
        f"📊 *רוחב שוק בתיק:* {report['up_count']} עלו | {report['down_count']} ירדו | {report['flat_count']} ללא שינוי"
    )
    lines.append("")
    lines.append("🚀 *מובילות היום:*")

    for item in report["top_gainers"]:
        icon = "🟢" if item["daily_pct"] >= 0 else "🔴"
        lines.append(
            f"• {icon} {escape_markdown(item['ticker'])} {escape_markdown(fmt_pct(item['daily_pct']))}"
        )

    lines.append("")
    lines.append("📉 *חלשות היום:*")

    for item in report["top_losers"]:
        icon = "🟢" if item["daily_pct"] >= 0 else "🔴"
        lines.append(
            f"• {icon} {escape_markdown(item['ticker'])} {escape_markdown(fmt_pct(item['daily_pct']))}"
        )

    if report["failed_tickers"]:
        lines.append("")
        lines.append(
            f"⚠️ *לא עודכנו:* {escape_markdown(', '.join(report['failed_tickers']))}"
        )

    lines.append("")
    lines.append(f"🧠 *תובנה:* {escape_markdown(build_insight(report))}")

    return "\n".join(lines)


def get_chart_trend(values: List[float]) -> str:
    if len(values) < 2 or values[0] == 0:
        return "ללא שינוי מהותי"

    change_pct = ((values[-1] - values[0]) / values[0]) * 100

    if change_pct > 3:
        return f"עלייה חזקה ({change_pct:.2f}%+)"
    if change_pct > 0:
        return f"עלייה מתונה ({change_pct:.2f}%+)"
    if change_pct < -3:
        return f"ירידה חדה ({change_pct:.2f}%)"
    if change_pct < 0:
        return f"ירידה מתונה ({change_pct:.2f}%)"
    return "ללא שינוי מהותי"


def build_chart(report: Dict, data, portfolio: List[Dict]) -> bytes:
    timeseries = get_portfolio_timeseries(data, portfolio)
    dates = [x[0] for x in timeseries]
    values = [x[1] for x in timeseries]

    if not dates or not values:
        raise ValueError("No chart data available")

    total_cost = report["total_cost"]
    profit_now = report["total_profit"]
    profit_pct_now = report["total_profit_pct"]
    trend = get_chart_trend(values)

    fig, ax = plt.subplots(figsize=(10.5, 5.8))

    ax.plot(dates, values, linewidth=2.6, label="Portfolio Value")
    ax.axhline(
        y=total_cost,
        linestyle="--",
        linewidth=1.8,
        alpha=0.8,
        label=f"Cost Basis (${total_cost:,.0f})",
    )

    ax.fill_between(
        dates,
        values,
        total_cost,
        where=[v >= total_cost for v in values],
        alpha=0.18,
        interpolate=True,
        label="Profit Zone",
    )

    ax.fill_between(
        dates,
        values,
        total_cost,
        where=[v < total_cost for v in values],
        alpha=0.10,
        interpolate=True,
        label="Below Cost",
    )

    max_idx = values.index(max(values))
    min_idx = values.index(min(values))

    ax.scatter(dates[max_idx], values[max_idx], s=70, zorder=5)
    ax.scatter(dates[min_idx], values[min_idx], s=70, zorder=5)

    ax.annotate(
        f"High\n${values[max_idx]:,.0f}",
        xy=(dates[max_idx], values[max_idx]),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        fontsize=9,
    )

    ax.annotate(
        f"Low\n${values[min_idx]:,.0f}",
        xy=(dates[min_idx], values[min_idx]),
        xytext=(0, -28),
        textcoords="offset points",
        ha="center",
        fontsize=9,
    )

    ax.set_title(
        f"Portfolio Value - Last 1 Month\n"
        f"Current Profit: ${profit_now:,.2f} ({profit_pct_now:.2f}%) | Trend: {trend}",
        fontsize=13,
        pad=14,
    )

    ax.set_xlabel("Date")
    ax.set_ylabel("Value ($)")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)

    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


def send_telegram_message(text: str) -> None:
    response = requests.post(
        telegram_api_url("sendMessage"),
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "MarkdownV2",
        },
        timeout=30,
    )
    response.raise_for_status()


def send_telegram_photo(photo_bytes: bytes, caption: str = "") -> None:
    files = {"photo": ("portfolio.png", photo_bytes, "image/png")}
    data = {
        "chat_id": TG_CHAT_ID,
        "caption": caption,
        "parse_mode": "MarkdownV2",
    }
    response = requests.post(
        telegram_api_url("sendPhoto"),
        data=data,
        files=files,
        timeout=60,
    )
    response.raise_for_status()


def main() -> None:
    require_env()

    portfolio = load_portfolio(PORTFOLIO_FILE)
    tickers = get_tickers(portfolio)

    data, failed_tickers = download_market_data(
        tickers,
        period="1mo",
        interval="1d",
    )

    report = analyze_portfolio(portfolio, data, failed_tickers)

    daily_summary = build_daily_summary(report)
    financial_summary = build_portfolio_summary(report)
    chart = build_chart(report, data, portfolio)

    send_telegram_message(daily_summary)

    current_value_text = f"${report['total_value']:,.2f}"
    total_profit_text = fmt_money(report["total_profit"])
    total_profit_pct_text = fmt_pct(report["total_profit_pct"])

    chart_caption = "\n".join(
        [
            "📈 *גרף שווי תיק \\- חודש אחרון*",
            f"💰 שווי נוכחי: {escape_markdown(current_value_text)}",
            f"📈 רווח כולל: {escape_markdown(total_profit_text)} ({escape_markdown(total_profit_pct_text)})",
        ]
    )

    send_telegram_photo(chart, caption=chart_caption)
    send_telegram_message(financial_summary)


if __name__ == "__main__":
    main()
