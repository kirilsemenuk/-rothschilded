import json
import os
from datetime import datetime, timezone

import matplotlib.pyplot as plt
import requests
import yfinance as yf

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

with open("portfolio.json", "r", encoding="utf-8") as f:
    portfolio = json.load(f)


def fmt_usd(value):
    return f"${value:,.2f}"


def fmt_pct(value):
    return f"{value:+.2f}%"


def fetch_quotes(symbols):
    data = yf.download(
        tickers=" ".join(symbols),
        period="2d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=False,
    )

    quotes = {}

    for symbol in symbols:
        try:
            if len(symbols) == 1:
                closes = data["Close"].dropna().tolist()
            else:
                closes = data[symbol]["Close"].dropna().tolist()

            if not closes:
                continue

            price = float(closes[-1])
            prev_close = float(closes[-2]) if len(closes) >= 2 else price

            quotes[symbol] = {
                "price": price,
                "prev_close": prev_close,
            }
        except Exception as e:
            print(f"Failed to parse quote for {symbol}: {e}")
            continue

    return quotes


def build_data():
    symbols = [p["ticker"].upper().strip() for p in portfolio]
    quotes = fetch_quotes(symbols)

    positions = []
    total_value = 0.0
    total_cost = 0.0
    total_day_pnl = 0.0
    missing = []

    for p in portfolio:
        symbol = p["ticker"].upper().strip()
        shares = float(p["shares"])
        avg_price = float(p["avg_price"])

        q = quotes.get(symbol)
        if q is None:
            missing.append(symbol)
            continue

        price = q["price"]
        prev_close = q["prev_close"]

        value = shares * price
        cost = shares * avg_price
        pnl = value - cost
        pnl_pct = ((price / avg_price) - 1) * 100 if avg_price else 0.0

        day_pnl = shares * (price - prev_close)
        day_pnl_pct = ((price / prev_close) - 1) * 100 if prev_close else 0.0

        total_value += value
        total_cost += cost
        total_day_pnl += day_pnl

        positions.append({
            "ticker": symbol,
            "shares": shares,
            "price": round(price, 2),
            "price_fmt": fmt_usd(price),
            "market_value": round(value, 2),
            "market_value_fmt": fmt_usd(value),
            "pnl": round(pnl, 2),
            "pnl_fmt": fmt_usd(pnl),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_pct_fmt": fmt_pct(pnl_pct),
            "day_pnl": round(day_pnl, 2),
            "day_pnl_fmt": fmt_usd(day_pnl),
            "day_pnl_pct": round(day_pnl_pct, 2),
            "day_pnl_pct_fmt": fmt_pct(day_pnl_pct),
        })

    positions.sort(key=lambda x: x["day_pnl"], reverse=True)

    top_winners = positions[:3]
    top_losers = sorted(positions, key=lambda x: x["day_pnl"])[:3]

    total_pnl = total_value - total_cost
    total_pnl_pct = ((total_value / total_cost) - 1) * 100 if total_cost else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_value": round(total_value, 2),
        "total_value_fmt": fmt_usd(total_value),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_fmt": fmt_usd(total_pnl),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "total_pnl_pct_fmt": fmt_pct(total_pnl_pct),
        "total_day_pnl": round(total_day_pnl, 2),
        "total_day_pnl_fmt": fmt_usd(total_day_pnl),
        "top_winners": top_winners,
        "top_losers": top_losers,
        "positions": positions,
        "missing_symbols": missing,
    }


def create_portfolio_chart():
    symbols = [p["ticker"].upper().strip() for p in portfolio]
    shares_map = {p["ticker"].upper().strip(): float(p["shares"]) for p in portfolio}

    data = yf.download(
        tickers=" ".join(symbols),
        period="1mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=False,
    )

    portfolio_series = None

    for symbol in symbols:
        try:
            if len(symbols) == 1:
                close_series = data["Close"].dropna()
            else:
                close_series = data[symbol]["Close"].dropna()

            weighted_series = close_series * shares_map[symbol]

            if portfolio_series is None:
                portfolio_series = weighted_series
            else:
                portfolio_series = portfolio_series.add(weighted_series, fill_value=0)
        except Exception as e:
            print(f"Failed to build chart series for {symbol}: {e}")
            continue

    if portfolio_series is None or portfolio_series.empty:
        print("Chart creation skipped: no data")
        return None

    plt.figure(figsize=(10, 5))
    plt.plot(portfolio_series.index, portfolio_series.values)
    plt.title("Portfolio Value - Last 1 Month")
    plt.xlabel("Date")
    plt.ylabel("Value ($)")
    plt.grid(True)
    plt.tight_layout()

    chart_path = "portfolio_chart.png"
    plt.savefig(chart_path, dpi=150)
    plt.close()

    return chart_path


def ask_groq(data):
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": (
                    "כתוב סיכום פיננסי מקצועי בעברית לטלגרם. "
                    "השתמש בסימני $ ו-% כשמתאימים. "
                    "מבנה: כותרת קצרה, 2-3 בולטים, ושורת סיכום אחת. "
                    "ציין שינוי יומי כולל בתיק, מניות מובילות ומניות חלשות, בלי חזרות ובלי מילים מיותרות."
                )
            },
            {
                "role": "user",
                "content": json.dumps(data, ensure_ascii=False)
            }
        ],
        "temperature": 0.4,
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    print("GROQ STATUS:", r.status_code)
    print("GROQ RESPONSE:", r.text[:1000])
    r.raise_for_status()

    resp = r.json()
    summary = resp["choices"][0]["message"]["content"].strip()
    return summary


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    print("TELEGRAM RESPONSE:", r.text)
    r.raise_for_status()
    return r.json()


def send_telegram_photo(photo_path, caption=None):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as photo:
        r = requests.post(
            url,
            data={
                "chat_id": TG_CHAT_ID,
                "caption": (caption or "")[:1024],
            },
            files={"photo": photo},
            timeout=60,
        )
    print("PHOTO RESPONSE:", r.text)
    r.raise_for_status()
    return r.json()


def main():
    data = build_data()
    print("DATA PREVIEW:", json.dumps(data, ensure_ascii=False)[:2000])

    if not data["positions"]:
        raise ValueError(f"No positions were built. Missing symbols: {data['missing_symbols']}")

    summary = ask_groq(data)
    chart_path = create_portfolio_chart()

    try:
        if chart_path:
            tg = send_telegram_photo(chart_path, caption=summary)
        else:
            tg = send_telegram(summary)
    except Exception as e:
        print(f"Photo send failed, falling back to text: {e}")
        tg = send_telegram(summary)

    print(json.dumps({
        "ok": True,
        "summary_preview": summary,
        "telegram": tg,
        "missing_symbols": data["missing_symbols"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
