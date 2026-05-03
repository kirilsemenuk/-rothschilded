from typing import Dict, List

from config import CHIP_TICKERS
from utils import safe_float


def build_positions_snapshot(portfolio: List[dict], prices: Dict[str, dict]) -> List[dict]:
    snapshot = []

    for item in portfolio:
        ticker = item["ticker"]
        shares = item["shares"]
        avg_price = item["avg_price"]

        if ticker not in prices:
            continue

        current_price = safe_float(prices[ticker]["price"])
        prev_close = safe_float(prices[ticker]["prev_close"], current_price)

        market_value = shares * current_price
        cost_basis = shares * avg_price
        total_profit = market_value - cost_basis
        total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

        daily_pnl = shares * (current_price - prev_close)
        daily_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        snapshot.append({
            "ticker": ticker,
            "name": prices[ticker].get("name", ticker),
            "shares": shares,
            "avg_price": avg_price,
            "current_price": current_price,
            "prev_close": prev_close,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "daily_pnl": daily_pnl,
            "daily_pct": daily_pct,
        })

    if not snapshot:
        raise RuntimeError("No valid positions after price fetch")

    return snapshot


def calculate_portfolio_metrics(snapshot: List[dict]) -> dict:
    portfolio_value = sum(item["market_value"] for item in snapshot)
    cost_basis = sum(item["cost_basis"] for item in snapshot)
    total_profit = portfolio_value - cost_basis
    total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

    daily_change = sum(item["daily_pnl"] for item in snapshot)
    prev_value = sum(item["shares"] * item["prev_close"] for item in snapshot)
    daily_change_pct = (daily_change / prev_value * 100) if prev_value else 0.0

    gainers = [item for item in snapshot if item["daily_pct"] > 0]
    losers = [item for item in snapshot if item["daily_pct"] < 0]
    unchanged = [item for item in snapshot if abs(item["daily_pct"]) < 1e-12]

    return {
        "portfolio_value": portfolio_value,
        "cost_basis": cost_basis,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
        "daily_change": daily_change,
        "daily_change_pct": daily_change_pct,
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "unchanged_count": len(unchanged),
        "top_gainer": max(snapshot, key=lambda x: x["daily_pct"], default=None),
        "top_impact": max(snapshot, key=lambda x: x["daily_pnl"], default=None),
        "worst_impact": min(snapshot, key=lambda x: x["daily_pnl"], default=None),
        "top_gainers": sorted(gainers, key=lambda x: x["daily_pct"], reverse=True)[:3],
        "top_losers": sorted(losers, key=lambda x: x["daily_pct"])[:3],
    }


def build_day_score(metrics: dict) -> float:
    score = 5.0
    score += min(max(metrics["daily_change_pct"] * 2.0, -3.0), 3.0)

    breadth = metrics["gainers_count"] - metrics["losers_count"]
    score += min(max(breadth * 0.25, -2.0), 2.0)

    if metrics.get("top_gainer") and metrics["top_gainer"]["daily_pct"] >= 3:
        score += 0.7

    return round(min(max(score, 0.0), 10.0), 1)


def build_daily_insight(metrics: dict) -> str:
    daily_change = metrics["daily_change"]
    top_impact = metrics.get("top_impact")
    top_gainers = metrics.get("top_gainers", [])

    if not top_impact:
        return "לא זוהתה תנועה משמעותית בתיק היום."

    leading_tickers = {item["ticker"] for item in top_gainers}
    chip_names = sorted(list(leading_tickers.intersection(CHIP_TICKERS)))

    if daily_change > 0 and chip_names:
        return f"מניות השבבים הובילו את היום, כש-{top_impact['ticker']} הייתה הדומיננטית ביותר בתיק."

    if daily_change > 0:
        return f"{top_impact['ticker']} הובילה את היום ותרמה הכי הרבה לעלייה בתיק."

    if daily_change < 0 and metrics.get("worst_impact"):
        return f"{metrics['worst_impact']['ticker']} הכבידה יותר מכולן על ביצועי התיק היום."

    return "התיק נסגר כמעט ללא שינוי, בלי מניה דומיננטית במיוחד."


def build_weekly_positions_snapshot(snapshot: list[dict], prices: dict) -> list[dict]:
    weekly_snapshot = []

    for item in snapshot:
        ticker = item["ticker"]

        if ticker not in prices:
            continue

        hist = prices[ticker]["hist"]

        if len(hist) < 2:
            continue

        current_price = item["current_price"]
        if len(hist) >= 7:
            week_start_price = hist["Close"].iloc[-5]
        else:
            week_start_price = hist["Close"].iloc[0]

        weekly_pnl = item["shares"] * (current_price - week_start_price)
        weekly_pct = ((current_price - week_start_price) / week_start_price * 100) if week_start_price else 0.0

        new_item = item.copy()
        new_item["week_start_price"] = week_start_price
        new_item["weekly_pnl"] = weekly_pnl
        new_item["weekly_pct"] = weekly_pct

        weekly_snapshot.append(new_item)

    if not weekly_snapshot:
        raise RuntimeError("No valid weekly positions")

    return weekly_snapshot


def calculate_weekly_metrics(weekly_snapshot: list[dict]) -> dict:
    portfolio_value = sum(item["market_value"] for item in weekly_snapshot)
    weekly_change = sum(item["weekly_pnl"] for item in weekly_snapshot)

    week_start_value = portfolio_value - weekly_change
    weekly_change_pct = (weekly_change / week_start_value * 100) if week_start_value else 0.0

    gainers = [item for item in weekly_snapshot if item["weekly_pct"] > 0]
    losers = [item for item in weekly_snapshot if item["weekly_pct"] < 0]
    unchanged = [item for item in weekly_snapshot if abs(item["weekly_pct"]) < 1e-12]

    return {
        "portfolio_value": portfolio_value,
        "weekly_change": weekly_change,
        "weekly_change_pct": weekly_change_pct,
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "unchanged_count": len(unchanged),
        "top_gainers": sorted(gainers, key=lambda x: x["weekly_pct"], reverse=True)[:3],
        "top_losers": sorted(losers, key=lambda x: x["weekly_pct"])[:3],
        "top_impact": max(weekly_snapshot, key=lambda x: x["weekly_pnl"], default=None),
        "worst_impact": min(weekly_snapshot, key=lambda x: x["weekly_pnl"], default=None),
    }