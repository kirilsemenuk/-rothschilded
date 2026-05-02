from datetime import datetime, timedelta
from typing import Dict, List

import yfinance as yf

from utils import safe_float


def fetch_prices_and_history(portfolio: List[dict], days: int = 30):
    tickers = [item["ticker"] for item in portfolio]
    prices: Dict[str, dict] = {}

    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=max(days * 3, 60))

    for ticker in tickers:
        print(f"Fetching {ticker}...")

        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(start=start_date, end=end_date, auto_adjust=False)

        if hist.empty:
            print(f"Warning: no data for {ticker}")
            continue

        hist = hist.dropna(subset=["Close"])

        if hist.empty:
            print(f"Warning: empty close data for {ticker}")
            continue

        current_price = safe_float(hist["Close"].iloc[-1])
        prev_close = current_price

        if len(hist) >= 2:
            prev_close = safe_float(hist["Close"].iloc[-2], current_price)

        info_name = ticker

        try:
            info = yf_ticker.info
            info_name = info.get("shortName") or info.get("longName") or ticker
        except Exception:
            info_name = ticker

        prices[ticker] = {
            "price": current_price,
            "prev_close": prev_close,
            "name": info_name,
            "hist": hist.tail(days),
        }

    if not prices:
        raise RuntimeError("Failed to fetch any market data")

    portfolio_history = build_portfolio_history(portfolio, prices, days=days)
    return prices, portfolio_history


def build_portfolio_history(portfolio: List[dict], prices: Dict[str, dict], days: int = 30):
    common_dates = None

    for item in portfolio:
        ticker = item["ticker"]

        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"].copy()
        hist = hist.dropna(subset=["Close"])

        if getattr(hist.index, "tz", None) is not None:
            hist.index = hist.index.tz_localize(None)

        ticker_dates = set(date.date() for date in hist.index)
        common_dates = ticker_dates if common_dates is None else common_dates.intersection(ticker_dates)

    if not common_dates:
        return []

    history = []

    for date_only in sorted(list(common_dates))[-days:]:
        total_value = 0.0

        for item in portfolio:
            ticker = item["ticker"]
            shares = item["shares"]

            if ticker not in prices:
                continue

            hist = prices[ticker]["hist"].copy()
            hist = hist.dropna(subset=["Close"])

            if getattr(hist.index, "tz", None) is not None:
                hist.index = hist.index.tz_localize(None)

            same_day = hist[hist.index.date == date_only]

            if same_day.empty:
                continue

            close_price = safe_float(same_day["Close"].iloc[-1])
            total_value += shares * close_price

        history.append({
            "date": datetime.combine(date_only, datetime.min.time()),
            "value": total_value,
        })

    return history
