import os
import sys
import json
import time
from typing import Any

import requests
import yfinance as yf
import matplotlib.pyplot as plt


with open("portfolio.json", "r", encoding="utf-8") as f:
    PORTFOLIO = json.load(f)

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)


ALERT_THRESHOLD = CONFIG["alert_threshold"]
GROQ_MODEL = CONFIG["groq_model"]
TOP_MOVERS_LIMIT = CONFIG["top_movers_limit"]
MESSAGE_TITLE = CONFIG["message_title"]
USE_AI_SUMMARY = CONFIG["use_ai_summary"]

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]


def get_price_data(ticker: str, mode: str) -> dict[str, Any] | None:
    stock = yf.Ticker(ticker)

    if mode == "daily":
        hist = stock.history(period="2d")
    elif mode == "weekly":
        hist = stock.history(period="5d")
    else:
        raise ValueError("Mode must be 'daily' or 'weekly'")

    if len(hist) < 2:
        return None

    prev_close = float(hist["Close"].iloc[-2])
    last_close = float(hist["Close"].iloc[-1])
    move_pct = ((last_close - prev_close) / prev_close) * 100

    return {
        "ticker": ticker,
        "prev_close": prev_close,
        "last_close": last_close,
        "move_pct": move_pct,
    }


def get_alert(move_pct: float) -> str:
    if move_pct >= ALERT_THRESHOLD:
        return "Strong rise"
    if move_pct <= -ALERT_THRESHOLD:
        return "Sharp drop"
    return ""


def build_portfolio_data(mode: str) -> dict[str, Any]:
    positions: list[dict[str, Any]] = []
    total_cost = 0.0
    total_value = 0.0

    for position in PORTFOLIO:
        ticker = position["ticker"]
        shares = float(position["shares"])
        avg_price = float(position["avg_price"])

        market_data = get_price_data(ticker, mode)

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

    top_movers = sorted(
        valid_positions,
        key=lambda p: abs(p["move_pct"]),
        reverse=True
    )[:TOP_MOVERS_LIMIT]

    alerts = [
        f'{p["ticker"]}: {p["alert"]} ({p["move_pct"]:+.2f}%)'
        for p in valid_positions
        if p["alert"]
    ]

    return {
        "positions": positions,
        "top_movers": top_movers,
        "alerts": alerts,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }


def build_raw_summary(data: dict[str, Any], mode: str) -> str:
    period_label = "Daily" if mode == "daily" else "Weekly"

    lines = [
        f"{period_label} portfolio summary",
        f'Portfolio value: ${data["total_value"]:.2f}',
        f'Total P/L: ${data["total_pnl"]:+.2f} ({data["total_pnl_pct"]:+.2f}%)',
        "",
        "Top movers:",
    ]

    if data["top_movers"]:
        for mover in data["top_movers"]:
            lines.append(f'- {mover["ticker"]}: {mover["move_pct"]:+.2f}%')
    else:
        lines.append("- No movers available")

    lines.append("")
    lines.append("Alerts:")

    if data["alerts"]:
        lines.extend(f"- {alert}" for alert in data["alerts"])
    else:
        lines.append("- No alerts")

    return "\n".join(lines)


def generate_ai_summary(raw_summary: str, mode: str) -> str:
    period_label = "daily" if mode == "daily" else "weekly"

    prompt = f"""
You are a portfolio assistant.

Write a short {period_label} portfolio update in plain English.
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
                    {
                        "role": "system",
                        "content": "You write concise portfolio summaries."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    },
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


def build_final_message(data: dict[str, Any], ai_summary: str | None, mode: str) -> str:
    period_label = "Daily" if mode == "daily" else "Weekly"
    lines = [f"{period_label} {MESSAGE_TITLE}", ""]

    if ai_summary:
        lines.append(ai_summary)
        lines.append("")

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


def get_chart_data(ticker: str, mode: str):
    stock = yf.Ticker(ticker)

    if mode == "daily":
        hist = stock.history(period="1d", interval="5m")
    elif mode == "weekly":
        hist = stock.history(period="5d", interval="1h")
    else:
        raise ValueError("Mode must be 'daily' or 'weekly'")

    if hist.empty:
        return None

    return hist


def create_chart(ticker: str, mode: str, output_path: str = "chart.png") -> str | None:
    hist = get_chart_data(ticker, mode)
    if hist is None or hist.empty:
        return None

    title = f"{ticker} - {'24H' if mode == 'daily' else 'Weekly'} Chart"

    plt.figure(figsize=(10, 5))
    plt.plot(hist.index, hist["Close"])
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    return output_path


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


def send_telegram_photo(image_path: str, caption: str = "") -> None:
    with open(image_path, "rb") as photo:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "caption": caption[:1024],
            },
            files={"photo": photo},
            timeout=30,
        )
    response.raise_for_status()


def run_report(mode: str) -> None:
    data = build_portfolio_data(mode)
    raw_summary = build_raw_summary(data, mode)

    ai_summary = None

    if mode == "weekly" and USE_AI_SUMMARY:
        try:
            ai_summary = generate_ai_summary(raw_summary, mode)
        except Exception as exc:
            print(f"AI summary failed: {exc}")

    final_message = build_final_message(data, ai_summary, mode)
    send_telegram_message(final_message)

    if mode == "weekly" and data["top_movers"]:
        top_ticker = data["top_movers"][0]["ticker"]
        chart_path = create_chart(top_ticker, mode)
        if chart_path:
            send_telegram_photo(chart_path, caption=f"Weekly chart: {top_ticker}")

    print(f"{mode.title()} report sent.")


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "daily"

    if mode not in {"daily", "weekly"}:
        raise ValueError("Mode must be 'daily' or 'weekly'")

    run_report(mode)
