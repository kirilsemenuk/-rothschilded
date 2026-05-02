import math


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def format_currency(value: float) -> str:
    if value > 0:
        return f"+${abs(value):,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${abs(value):,.2f}"


def format_currency_plain(value: float) -> str:
    return f"${abs(value):,.2f}"


def format_percent(value: float) -> str:
    if value > 0:
        return f"+{value:.2f}%"
    if value < 0:
        return f"{value:.2f}%"
    return f"{value:.2f}%"


def get_dot_emoji(value: float) -> str:
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
