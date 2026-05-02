from typing import List, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from portfolio_service import build_day_score, build_daily_insight
from utils import (
    format_currency,
    format_currency_plain,
    format_percent,
    get_dot_emoji,
    get_status_text,
)


def build_daily_summary_message(metrics: dict, high_30d: Optional[float], low_30d: Optional[float]) -> str:
    status_emoji = get_dot_emoji(metrics["daily_change"])
    day_score = build_day_score(metrics)
    insight = build_daily_insight(metrics)

    winners_lines = [
        f"• {get_dot_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}"
        for item in metrics["top_gainers"]
    ] or ["• אין"]

    losers_lines = [
        f"• {get_dot_emoji(item['daily_pct'])} {item['ticker']} {format_percent(item['daily_pct'])}"
        for item in metrics["top_losers"]
    ] or ["• אין"]

    top_impact_line = "—"

    if metrics.get("top_impact"):
        top_impact_line = f"{metrics['top_impact']['ticker']} {format_currency(metrics['top_impact']['daily_pnl'])}"

    lines = [
        "📊 סיכום יומי – Rothschild",
        "",
        f"{status_emoji} מצב: {get_status_text(metrics['daily_change'])}",
        f"💰 שווי תיק: {format_currency_plain(metrics['portfolio_value'])}",
        f"📈 רווח כולל: {format_currency(metrics['total_profit'])} ({format_percent(metrics['total_profit_pct'])})",
        f"🟢 שינוי יומי: {format_currency(metrics['daily_change'])} ({format_percent(metrics['daily_change_pct'])})",
        f"🎯 ציון יום: {day_score}/10",
        "",
        "──────────────",
        "",
        f"💵 הכי השפיעה: {top_impact_line}",
        "",
        f"📊 רוחב שוק בתיק: {metrics['gainers_count']} עלו | {metrics['losers_count']} ירדו | {metrics['unchanged_count']} ללא שינוי",
        "",
        "🚀 מובילות היום:",
        *winners_lines,
        "",
        "📉 חלשות היום:",
        *losers_lines,
        "",
        f"🧠 תובנה: {insight}",
    ]

    if high_30d is not None or low_30d is not None:
        lines.extend([
            "",
            "📍 שיא ושפל (30 יום):",
            f"🔺 שיא: {format_currency_plain(high_30d) if high_30d is not None else '—'}",
            f"🔻 שפל: {format_currency_plain(low_30d) if low_30d is not None else '—'}",
        ])

    return "\n".join(lines)


def build_chart_caption() -> str:
    return "📈 גרף שווי תיק - 30 ימים אחרונים"


def create_portfolio_chart(history: List[dict], cost_basis: float, output_path: str = "portfolio_chart.png"):
    if not history:
        raise ValueError("No portfolio history to plot")

    dates = [item["date"] for item in history]
    values = [item["value"] for item in history]

    high_value = max(values)
    low_value = min(values)
    today_value = values[-1]

    high_idx = values.index(high_value)
    low_idx = values.index(low_value)
    today_idx = len(values) - 1

    current_profit = today_value - cost_basis
    current_profit_pct = (current_profit / cost_basis * 100) if cost_basis else 0.0

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12.5, 6.8), dpi=170)

    fig.patch.set_facecolor("#0f1117")
    ax.set_facecolor("#171b26")

    ax.plot(dates, values, linewidth=2.8, color="#6ea8fe", label="Portfolio Value", zorder=3)
    ax.fill_between(dates, values, min(values) * 0.98, color="#6ea8fe", alpha=0.12, zorder=1)

    ax.axhline(
        cost_basis,
        linestyle="--",
        linewidth=1.4,
        color="#9aa4b2",
        alpha=0.9,
        label=f"Cost Basis (${cost_basis:,.0f})",
        zorder=2,
    )

    ax.scatter(dates[high_idx], high_value, s=85, color="#22c55e", edgecolors="white", linewidth=0.8, zorder=5)
    ax.scatter(dates[low_idx], low_value, s=85, color="#ef4444", edgecolors="white", linewidth=0.8, zorder=5)
    ax.scatter(dates[today_idx], today_value, s=95, color="#f59e0b", edgecolors="white", linewidth=0.9, zorder=6)

    ax.annotate(f"HIGH\n${high_value:,.0f}", (dates[high_idx], high_value), textcoords="offset points", xytext=(0, 14), ha="center", fontsize=9, fontweight="bold", color="#22c55e")
    ax.annotate(f"LOW\n${low_value:,.0f}", (dates[low_idx], low_value), textcoords="offset points", xytext=(0, -34), ha="center", fontsize=9, fontweight="bold", color="#ef4444")
    ax.annotate(f"TODAY\n${today_value:,.0f}", (dates[today_idx], today_value), textcoords="offset points", xytext=(0, 14), ha="center", fontsize=9, fontweight="bold", color="#f59e0b")

    ax.set_title(
        "Portfolio Value • Last 30 Days\n"
        f"Current Profit: {'+' if current_profit > 0 else ''}${current_profit:,.2f} "
        f"({'+' if current_profit_pct > 0 else ''}{current_profit_pct:.2f}%)",
        fontsize=15,
        fontweight="bold",
        pad=18,
        color="white",
    )

    ax.set_xlabel("Date", fontsize=10, color="#cbd5e1", labelpad=10)
    ax.set_ylabel("Value ($)", fontsize=10, color="#cbd5e1", labelpad=10)
    ax.tick_params(axis="x", colors="#cbd5e1", labelsize=9)
    ax.tick_params(axis="y", colors="#cbd5e1", labelsize=9)

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.18)

    for spine in ax.spines.values():
        spine.set_color("#2a3242")
        spine.set_linewidth(1.0)

    ax.legend(loc="upper left", frameon=True, fancybox=True, framealpha=0.18, facecolor="#0f1117", edgecolor="#334155", fontsize=9)

    y_min = min(min(values), cost_basis) * 0.96
    y_max = max(max(values), cost_basis) * 1.04
    ax.set_ylim(y_min, y_max)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    return output_path, high_value, low_value
