import os
import requests
import yfinance as yf

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

PORTFOLIO = [
    {"ticker": "AAPL", "shares": 1, "avg_price": 180},
    {"ticker": "AMAT", "shares": 1, "avg_price": 410},
    {"ticker": "IBIT", "shares": 2, "avg_price": 95},
    {"ticker": "INTC", "shares": 0.5168, "avg_price": 180},
    {"ticker": "NVO", "shares": 1, "avg_price": 410},
    {"ticker": "EWY", "shares": 3, "avg_price": 95},
    {"ticker": "RGTI", "shares": 1, "avg_price": 180},
    {"ticker": "TD", "shares": 10, "avg_price": 410},
    {"ticker": "SEDG", "shares": 2, "avg_price": 95},
    {"ticker": "TEVA", "shares": 5, "avg_price": 180},
    {"ticker": "PEP", "shares": 9, "avg_price": 410},
    {"ticker": "IAU", "shares": 5.2641, "avg_price": 180},
    {"ticker": "VOO", "shares": 3.8485, "avg_price": 410},
    {"ticker": "NVDA", "shares": 1, "avg_price": 95},
]

ALERT_THRESHOLD = 3.0


def get_price_data(ticker: str):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")

    if len(hist) < 2:
        return None

    prev_close = hist["Close"].iloc[-2]
    last_close = hist["Close"].iloc[-1]
    change_pct = ((last_close - prev_close) / prev_close) * 100

    return {
        "ticker": ticker,
        "last_close": float(last_close),
        "change_pct": float(change_pct),
    }


def get_alert(change_pct: float) -> str:
    if change_pct >= ALERT_THRESHOLD:
        return "Strong rise"
    if change_pct <= -ALERT_THRESHOLD:
        return "Sharp drop"
    return ""


def build_portfolio_summary() -> str:
    lines = []
    total_cost = 0.0
    total_value = 0.0
    alerts = []

    for position in PORTFOLIO:
        ticker = position["ticker"]
        shares = position["shares"]
        avg_price = position["avg_price"]

        market_data = get_price_data(ticker)
        if not market_data:
            lines.append(f"{ticker}: not enough data")
            continue

        last_price = market_data["last_close"]
        change_pct = market_data["change_pct"]

        cost_basis = shares * avg_price
        market_value = shares * last_price
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis) * 100 if cost_basis else 0.0

        total_cost += cost_basis
        total_value += market_value

        alert = get_alert(change_pct)
        line = (
            f"{ticker}: shares={shares}, price=${last_price:.2f}, "
            f"move={change_pct:+.2f}%, pnl=${pnl:+.2f} ({pnl_pct:+.2f}%)"
        )

        if alert:
            line += f", alert={alert}"
            alerts.append(f"{ticker}: {alert} ({change_pct:+.2f}%)")

        lines.append(line)

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost else 0.0

    footer = [
        "",
        f"Total market value: ${total_value:.2f}",
        f"Total P/L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)",
        "",
        "Alerts:",
    ]

    if alerts:
        footer.extend(alerts)
    else:
        footer.append("No alerts")

    return "\n".join(lines + footer)


def generate_ai_summary(summary_text: str) -> str:
    prompt = f"""
You are a portfolio assistant.

Write a short weekly summary in plain English.
Keep it concise: 4-6 lines.
Focus on the biggest movers, overall portfolio direction, and anything notable.
Do not give financial advice.
Do not invent reasons not present in the data.

Portfolio data:
{summary_text}
""".strip()

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4.1-mini",
            "messages": [
                {"role": "system", "content": "You write concise portfolio summaries."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def send_telegram_message(text: str):
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    response.raise_for_status()


def weekly_report():
    raw_summary = build_portfolio_summary()
    ai_summary = generate_ai_summary(raw_summary)

    final_message = f"{ai_summary}\n\nRaw data:\n{raw_summary}"
    send_telegram_message(final_message)


if __name__ == "__main__":
    weekly_report()
