import traceback

from config import DAYS_HISTORY, PORTFOLIO_JSON
from data_fetcher import fetch_prices_and_history
from portfolio_loader import load_portfolio
from portfolio_service import build_positions_snapshot, calculate_portfolio_metrics
from report_generator import (
    build_chart_caption,
    build_daily_summary_message,
    create_portfolio_chart,
)
from telegram_client import send_error_to_telegram, send_telegram_message, send_telegram_photo


def main():
    print("Loading portfolio...")
    portfolio = load_portfolio(PORTFOLIO_JSON)

    print("Fetching market data...")
    prices, history = fetch_prices_and_history(portfolio, days=DAYS_HISTORY)
    print(f"Fetched data for {len(prices)} tickers.")

    print("Calculating snapshot...")
    snapshot = build_positions_snapshot(portfolio, prices)
    metrics = calculate_portfolio_metrics(snapshot)

    print("Building chart...")
    chart_path, high_30d, low_30d = create_portfolio_chart(
        history=history,
        cost_basis=metrics["cost_basis"],
        output_path="portfolio_chart.png",
    )

    print("Building messages...")
    daily_message = build_daily_summary_message(
        metrics=metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )
    chart_caption = build_chart_caption()

    print("Sending chart...")
    send_telegram_photo(chart_path, caption=chart_caption)

    print("Sending daily summary...")
    send_telegram_message(daily_message)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback_text = traceback.format_exc()
        print(traceback_text)
        send_error_to_telegram(traceback_text)
        raise
