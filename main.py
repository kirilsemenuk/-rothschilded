import traceback

from config import DAYS_HISTORY, PORTFOLIO_JSON, REPORT_MODE
from data_fetcher import fetch_prices_and_history
from portfolio_loader import load_portfolio
from portfolio_service import (
    build_positions_snapshot,
    calculate_portfolio_metrics,
    build_weekly_positions_snapshot,
    calculate_weekly_metrics,
)
from report_generator import (
    build_chart_caption,
    build_daily_summary_message,
    build_weekly_summary_message,
    create_portfolio_chart,
)
from telegram_client import send_error_to_telegram, send_telegram_message, send_telegram_photo


def run_daily_report():
    print("Loading portfolio...")
    portfolio = load_portfolio(PORTFOLIO_JSON)

    print("Fetching market data...")
    prices, history = fetch_prices_and_history(portfolio, days=DAYS_HISTORY)

    print("Calculating daily metrics...")
    snapshot = build_positions_snapshot(portfolio, prices)
    metrics = calculate_portfolio_metrics(snapshot)

    print("Creating chart...")
    chart_path, high_30d, low_30d = create_portfolio_chart(
        history=history,
        cost_basis=metrics["cost_basis"],
        output_path="portfolio_chart.png",
    )

    print("Building daily message...")
    message = build_daily_summary_message(
        metrics=metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )

    print("Sending chart...")
    send_telegram_photo(chart_path, caption=build_chart_caption())

    print("Sending daily summary...")
    send_telegram_message(message)

    print("Daily report done.")


def run_weekly_report():
    print("Loading portfolio...")
    portfolio = load_portfolio(PORTFOLIO_JSON)

    print("Fetching market data...")
    prices, history = fetch_prices_and_history(portfolio, days=DAYS_HISTORY)

    print("Calculating weekly metrics...")
    snapshot = build_positions_snapshot(portfolio, prices)
    weekly_snapshot = build_weekly_positions_snapshot(snapshot, prices)
    metrics = calculate_weekly_metrics(weekly_snapshot)

    print("Creating chart...")
    chart_path, high_30d, low_30d = create_portfolio_chart(
        history=history,
        cost_basis=sum(item["cost_basis"] for item in weekly_snapshot),
        output_path="portfolio_weekly_chart.png",
    )

    print("Building weekly message...")
    message = build_weekly_summary_message(
        metrics=metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )

    print("Sending chart...")
    send_telegram_photo(chart_path, caption="📈 גרף שבועי / 30 ימים אחרונים")

    print("Sending weekly summary...")
    send_telegram_message(message)

    print("Weekly report done.")

def main():
    mode = REPORT_MODE.lower().strip()

    if mode == "daily":
        run_daily_report()
    elif mode == "weekly":
        run_weekly_report()
    else:
        raise ValueError(f"Unsupported REPORT_MODE: {REPORT_MODE}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        print(error_text)
        send_error_to_telegram(error_text)
        raise

    