import json
from datetime import datetime
from typing import Dict, List, Tuple


CHIP_TICKERS = {"AMD", "NVDA", "INTC", "AMAT", "TSM", "AVGO", "MU", "QCOM"}


def load_portfolio(path: str = "portfolio.json") -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_currency(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


def format_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def get_change_emoji(value: float) -> str:
    if value > 0:
        return "🟢"
    if value < 0:
        return "🔴"
    return "⚪️"


def get_status_text(daily_change: float) -> str:
    if daily_change > 0:
        return "יום חיובי"
    if daily_change < 0:
        return "יום שלילי"
    return "ללא שינוי"


def build_positions_snapshot(
    portfolio: List[dict],
    prices: Dict[str, dict],
) -> List[dict]:
    """
    prices format:
    {
        "AMD": {"price": 125.25, "prev_close": 120.64},
        "NVDA": {"price": 133.74, "prev_close": 130.56},
        ...
    }
    """
    snapshot = []

    for item in portfolio:
        ticker = item["ticker"].upper()
        shares = float(item["shares"])
        avg_price = float(item["avg_price"])

        if ticker not in prices:
            continue

        current_price = float(prices[ticker]["price"])
        prev_close = float(prices[ticker]["prev_close"])

        market_value = shares * current_price
        cost_basis = shares * avg_price
        total_profit = market_value - cost_basis
        total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

        daily_pnl = shares * (current_price - prev_close)
        daily_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        snapshot.append({
            "ticker": ticker,
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

    return snapshot


def calculate_portfolio_metrics(snapshot: List[dict]) -> dict:
    portfolio_value = sum(x["market_value"] for x in snapshot)
    cost_basis = sum(x["cost_basis"] for x in snapshot)
    total_profit = portfolio_value - cost_basis
    total_profit_pct = (total_profit / cost_basis * 100) if cost_basis else 0.0

    daily_change = sum(x["daily_pnl"] for x in snapshot)
    prev_value = sum(x["shares"] * x["prev_close"] for x in snapshot)
    daily_change_pct = (daily_change / prev_value * 100) if prev_value else 0.0

    gainers = [x for x in snapshot if x["daily_pct"] > 0]
    losers = [x for x in snapshot if x["daily_pct"] < 0]
    unchanged = [x for x in snapshot if abs(x["daily_pct"]) < 1e-9]

    top_gainer = max(snapshot, key=lambda x: x["daily_pct"], default=None)
    top_impact = max(snapshot, key=lambda x: x["daily_pnl"], default=None)

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
        "top_gainer": top_gainer,
        "top_impact": top_impact,
        "top_gainers": sorted(gainers, key=lambda x: x["daily_pct"], reverse=True)[:3],
        "top_losers": sorted(losers, key=lambda x: x["daily_pct"])[:3],
    }


def build_daily_insight(metrics: dict) -> str:
    top_gainers = metrics["top_gainers"]
    top_impact = metrics["top_impact"]
    daily_change = metrics["daily_change"]

    if not top_impact:
        return "לא זוהתה תנועה משמעותית היום."

    top_gainer_tickers = {x["ticker"] for x in top_gainers}
    chip_names = top_gainer_tickers.intersection(CHIP_TICKERS)

    if chip_names and daily_change > 0:
        joined = ", ".join(sorted(chip_names))
        return f"סקטור השבבים הוביל את העלייה היום ({joined}), כאשר {top_impact['ticker']} תרמה הכי הרבה לתיק."

    if daily_change > 0:
        return f"{top_impact['ticker']} הייתה בעלת ההשפעה הדולרית הגבוהה ביותר היום ודחפה את התיק לעלייה."

    if daily_change < 0:
        return f"{top_impact['ticker']} הייתה הגורם המרכזי להשפעה על התיק היום, על רקע יום חלש יותר."

    return "התיק סיים את היום כמעט ללא שינוי, ללא מניה דומיננטית במיוחד."


def build_score(metrics: dict) -> float:
    """
    ציון יום פשוט בין 0 ל-10
    """
    score = 5.0

    # שינוי יומי
    score += min(max(metrics["daily_change_pct"] * 2.0, -3.0), 3.0)

    # רוחב שוק
    breadth = metrics["gainers_count"] - metrics["losers_count"]
    score += min(max(breadth * 0.25, -2.0), 2.0)

    # בונוס על מניה מובילה חזקה
    if metrics["top_gainer"] and metrics["top_gainer"]["daily_pct"] >= 3:
        score += 0.7

    return round(min(max(score, 0), 10), 1)


def build_daily_summary_message(
    metrics: dict,
    high_30d: float | None = None,
    low_30d: float | None = None,
) -> str:
    status_emoji = get_change_emoji(metrics["daily_change"])
    daily_score = build_score(metrics)
    insight = build_daily_insight(metrics)

    winners_lines = []
    for item in metrics["top_gainers"]:
        winners_lines.append(f"• {get_change_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}")

    losers_lines = []
    for item in metrics["top_losers"]:
        losers_lines.append(f"• {get_change_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}")

    top_gainer_line = "—"
    if metrics["top_gainer"]:
        top_gainer_line = f"{metrics['top_gainer']['ticker']} {format_percent(metrics['top_gainer']['daily_pct'])}"

    top_impact_line = "—"
    if metrics["top_impact"]:
        top_impact_line = f"{metrics['top_impact']['ticker']} ({format_currency(metrics['top_impact']['daily_pnl'])} לתיק)"

    lines = [
        "📊 סיכום יומי – Rothschild",
        "",
        f"{status_emoji} מצב התיק: {get_status_text(metrics['daily_change'])}",
        f"💰 שווי תיק: {format_currency(metrics['portfolio_value'])}",
        f"📈 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})",
        f"🟢 שינוי יומי: {format_currency(metrics['daily_change'])} ({format_percent(metrics['daily_change_pct'])})",
        f"🎯 ציון יום: {daily_score}/10",
        "",
        "──────────────",
        "",
        f"🏆 מניה בולטת היום: {top_gainer_line}",
        f"💵 השפעה דולרית מובילה: {top_impact_line}",
        "",
        f"📊 רוחב שוק בתיק: {metrics['gainers_count']} עלו | {metrics['losers_count']} ירדו | {metrics['unchanged_count']} ללא שינוי",
        "",
        "🚀 מובילות היום:",
        *(winners_lines if winners_lines else ["• אין"]),
        "",
        "📉 חלשות היום:",
        *(losers_lines if losers_lines else ["• אין"]),
        "",
        f"🧠 תובנה: {insight}",
    ]

    if high_30d is not None or low_30d is not None:
        lines.extend([
            "",
            "📍 נקודות מפתח:",
            f"🔺 שיא 30 יום: {format_currency(high_30d) if high_30d is not None else '—'}",
            f"🔻 שפל 30 יום: {format_currency(low_30d) if low_30d is not None else '—'}",
        ])

    return "\n".join(lines)


def build_chart_caption(
    portfolio_value: float,
    total_profit: float,
    total_profit_pct: float,
) -> str:
    return (
        "📈 גרף שווי תיק - 30 ימים אחרונים\n\n"
        f"💰 שווי נוכחי: {format_currency(portfolio_value)}\n"
        f"📊 רווח כולל: {format_currency(total_profit)} ({format_percent(total_profit_pct)})"
    )


# =========================
# דוגמת שימוש מלאה
# =========================

if __name__ == "__main__":
    # טוען את התיק מהקובץ שלך
    portfolio = load_portfolio("portfolio.json")

    # דוגמת מחירים בלבד.
    # כאן תדביק את המחירים שאתה כבר מביא מ-yfinance
    prices = {
        "AAPL": {"price": 135.97, "prev_close": 136.61},
        "AMD": {"price": 125.25, "prev_close": 120.64},
        "AMAT": {"price": 162.90, "prev_close": 162.14},
        "IBIT": {"price": 39.00, "prev_close": 38.80},
        "INTC": {"price": 19.98, "prev_close": 19.66},
        "NVO": {"price": 46.90, "prev_close": 46.58},
        "EWY": {"price": 120.51, "prev_close": 121.67},
        "RGTI": {"price": 7.90, "prev_close": 7.74},
        "TD": {"price": 83.10, "prev_close": 82.83},
        "SEDG": {"price": 19.05, "prev_close": 18.88},
        "TEVA": {"price": 24.33, "prev_close": 24.50},
        "PEP": {"price": 153.25, "prev_close": 152.89},
        "IAU": {"price": 76.22, "prev_close": 75.99},
        "VOO": {"price": 612.20, "prev_close": 609.75},
        "NVDA": {"price": 133.73, "prev_close": 130.56},
    }

    snapshot = build_positions_snapshot(portfolio, prices)
    metrics = calculate_portfolio_metrics(snapshot)

    # אם יש לך נתוני היסטוריה של 30 יום, תכניס כאן
    high_30d = 5700.00
    low_30d = 5212.00

    daily_message = build_daily_summary_message(
        metrics=metrics,
        high_30d=high_30d,
        low_30d=low_30d,
    )

    chart_caption = build_chart_caption(
        portfolio_value=metrics["portfolio_value"],
        total_profit=metrics["total_profit"],
        total_profit_pct=metrics["total_profit_pct"],
    )

    print("=== DAILY MESSAGE ===")
    print(daily_message)
    print()
    print("=== CHART CAPTION ===")
    print(chart_caption)
