import json
import os
from datetime import datetime, timezone

import requests
import yfinance as yf

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

with open("portfolio.json", "r", encoding="utf-8") as f:
    portfolio = json.load(f)


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
        except Exception:
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
            "price": round(price, 2),
            "market_value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "day_pnl": round(day_pnl, 2),
            "day_pnl_pct": round(day_pnl_pct, 2),
        })

    positions.sort(key=lambda x: x["market_value"], reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_value - total_cost, 2),
        "total_day_pnl": round(total_day_pnl, 2),
        "positions": positions,
        "missing_symbols": missing,
    }


def ask_groq(data):
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": (
                    "כתוב סיכום יומי קצר בעברית לטלגרם. "
                    "כותרת אחת, עד 3 בולטים, ושורת סיכום אחת. "
                    "ציין את השינוי היומי בתיק ואת המניות הבולטות."
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
    r.raise_for_status()
    resp = r.json()
    return resp["choices"][0]["message"]["content"].strip()


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
    r.raise_for_status()
    return r.json()


def main():
    data = build_data()
    summary = ask_groq(data)
    tg = send_telegram(summary)
    print(json.dumps({
        "ok": True,
        "summary_preview": summary,
        "telegram": tg,
        "missing_symbols": data["missing_symbols"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
