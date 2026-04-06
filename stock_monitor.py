import time
import requests
import schedule
import yfinance as yf
##TICKERS = ["AAPL", "AMAT", "IBIT", "INTC", "NVO", "EWY", "RGTI", "TD", "SEDG", "TEVA", "PEP", "IAU", "VOO", "NVDA"]

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
    {"ticker": "PEP", "shares": 2.011, "avg_price": 95},
    {"ticker": "IAU", "shares": 5.2641, "avg_price": 180},
    {"ticker": "VOO", "shares": 3.8485, "avg_price": 410},
    {"ticker": "NVDA", "shares": 1, "avg_price": 95},
]

BOT_TOKEN = "8402510483:AAFXomjkwHKYLYbvjHm1E4MTD0nVjI6OxJE"
CHAT_ID = "750575430"
ALERT_THRESHOLD = 3.0


def get_price_data(ticker: str):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="2d")

    if len(hist) < 2:
        return None

    prev_close = hist["Close"].iloc[-2]
    last_close = hist["Close"].iloc[-1]
    change_pct = ((last_close - prev_close) / prev_close) * 100

    return {
        "ticker": ticker,
        "prev_close": float(prev_close),
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
    lines = ["Weekly portfolio summary", ""]
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
            f"{ticker}: {shares} shares | "
            f"Price ${last_price:.2f} | "
            f"Day {change_pct:+.2f}% | "
            f"P/L ${pnl:+.2f} ({pnl_pct:+.2f}%)"
        )

        if alert:
            line += f" | {alert}"
            alerts.append(f"{ticker}: {alert} ({change_pct:+.2f}%)")

        lines.append(line)

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost else 0.0

    lines.append("")
    lines.append("Total portfolio")
    lines.append(f"Cost basis: ${total_cost:.2f}")
    lines.append(f"Market value: ${total_value:.2f}")
    lines.append(f"Total P/L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")

    lines.append("")
    lines.append("Alerts")
    if alerts:
        lines.extend(f"- {alert}" for alert in alerts)
    else:
        lines.append("- No alerts this week")

    return "\n".join(lines)


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()


def weekly_report():
    summary = build_portfolio_summary()
    send_telegram_message(summary)
    print("Weekly report sent.")


schedule.every().sunday.at("18:00").do(weekly_report)

print("Scheduler started...")

while True:
    schedule.run_pending()
    time.sleep(30)