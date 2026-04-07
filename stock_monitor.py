import os
import time
from typing import Any

import requests
import yfinance as yf
import json

with open("portfolio.json", "r") as f:
    portfolio = json.load(f)


BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

ALERT_THRESHOLD = 3.0
GROQ_MODEL = "llama-3.3-70b-versatile"


def get_price_data(ticker: str) -> dict[str, Any] | None:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")

    if len(hist) < 2:
        return None

    prev_close = float(hist["Close"].iloc[-2])
    last_close = float(hist["Close"].iloc[-1])
    move_pct = ((last_close - prev_close) / prev_close) * 100

    return {
        "ticker": ticker,
        "prev_close": prev_close,
        "last_close": last_close,
        "move_pct": float(move_pct),
    }


def get_alert(move_pct: float) -> str:
    if move_pct >= ALERT_THRESHOLD:
        return "Strong rise"
    if move_pct <= -ALERT_THRESHOLD:
        return "Sharp drop"
    return ""


def build_portfolio_data() -> dict[str, Any]:
    positions: list[dict[str, Any]] = []
    total_cost = 0.0
    total_value = 0.0

    for position in PORTFOLIO:
        ticker = position["ticker"]
        shares = float(position["shares"])
        avg_price = float(position["avg_price"])

        market_data = get_price_data(ticker)
        if not market_data:
            positions.append(
                {
                    "ticker": ticker,
                    "shares": shares,
                    "price": None,
                    "move_pct": None,
                    "cost_basis": shares * avg_price,
                    "market_value": None,
                    "pnl": None,
                    "pnl_pct": None,
                    "alert": "Not enough data",
                }
            )
            continue

        last_price = market_data["last_close"]
        move_pct = market_data["move_pct"]

        cost_basis = shares * avg_price
        market_value = shares * last_price
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis) * 100 if cost_basis else 0.0
        alert = get_alert(move_pct)

        total_cost += cost_basis
        total_value += market_value

        positions.append(
            {
                "ticker": ticker,
                "shares": shares,
                "price": last_price,
                "move_pct": move_pct,
                "cost_basis": cost_basis,
                "market_value": market_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "alert": alert,
            }
        )

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost else 0.0

    valid_positions = [p for p in positions if p["move_pct"] is not None]
    top_movers = sorted(valid_positions, key=lambda p: abs(p["move_pct"]), reverse=True)[:3]

    alerts = [f'{p["ticker"]}: {p["alert"]} ({p["move_pct"]:+.2f}%)'
              for p in valid_positions if p["alert"]]

    return {
        "positions": positions,
        "top_movers": top_movers,
        "alerts": alerts,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


def build_raw_summary(data: dict[str, Any]) -> str:
    top_movers = data["top_movers"]
    alerts = data["alerts"]

    lines = [
        f'Portfolio value: ${data["total_value"]:.2f}',
        f'Total P/L: ${data["total_pnl"]:+.2f} ({data["total_pnl_pct"]:+.2f}%)',
        "",
        "Top movers:",
    ]

    if top_movers:
        for mover in top_movers:
            lines.append(f'- {mover["ticker"]}: {mover["move_pct"]:+.2f}%')
    else:
        lines.append("- No movers available")

    lines.append("")
    lines.append("Alerts:")
    if alerts:
        lines.extend(f"- {alert}" for alert in alerts)
    else:
        lines.append("- No alerts")

    return "\n".join(lines)


def generate_ai_summary(raw_summary: str) -> str:
    prompt = f"""
You are a portfolio assistant.

Write a short portfolio update in plain English.
Keep it under 6 lines.
Mention:
1. overall portfolio direction
2. strongest mover
3. any notable weakness
4. one focus point

Do not give financial advice.
Do not invent news or reasons not present in the data.

Portfolio data:
{raw_summary}
""".strip()

    for attempt in range(3):
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You write concise portfolio summaries."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
            timeout=60,
        )

        if response.status_code == 429 and attempt < 2:
            time.sleep(2 ** attempt)
            continue

        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()

    raise RuntimeError("Groq summary failed after retries")


def build_final_message(data: dict[str, Any], ai_summary: str | None) -> str:
    lines = []

    if ai_summary:
        lines.append(ai_summary)
        lines.append("")

    lines.append("Portfolio Snapshot")
    lines.append(f'Value: ${data["total_value"]:.2f}')
    lines.append(f'Total P/L: ${data["total_pnl"]:+.2f} ({data["total_pnl_pct"]:+.2f}%)')
    lines.append("")

    lines.append("Top Movers")
    if data["top_movers"]:
        for mover in data["top_movers"]:
            lines.append(f'- {mover["ticker"]}: {mover["move_pct"]:+.2f}%')
    else:
        lines.append("- No movers available")

    lines.append("")
    lines.append("Alerts")
    if data["alerts"]:
        lines.extend(f"- {alert}" for alert in data["alerts"])
    else:
        lines.append("- No alerts")

    return "\n".join(lines)


def send_telegram_message(text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text[:3500],
        },
        timeout=30,
    )
    response.raise_for_status()


def weekly_report() -> None:
    data = build_portfolio_data()
    raw_summary = build_raw_summary(data)

    ai_summary = None
    try:
        ai_summary = generate_ai_summary(raw_summary)
    except Exception as exc:
        print(f"AI summary failed: {exc}")

    final_message = build_final_message(data, ai_summary)
    send_telegram_message(final_message)
    print("Portfolio report sent.")


if __name__ == "__main__":
    weekly_report()
