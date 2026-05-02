import json
from typing import List

from utils import safe_float


def load_portfolio(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("portfolio.json must contain a list of holdings")

    portfolio = []

    for item in data:
        ticker = str(item["ticker"]).upper().strip()
        shares = safe_float(item["shares"])
        avg_price = safe_float(item["avg_price"])

        if not ticker or shares <= 0:
            continue

        portfolio.append({
            "ticker": ticker,
            "shares": shares,
            "avg_price": avg_price,
        })

    if not portfolio:
        raise ValueError("Portfolio is empty or invalid")

    return portfolio
