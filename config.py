import os


def get_env(name: str, default=None, required: bool = False):
    value = os.getenv(name, default)

    if required and not value:
        raise RuntimeError(f"Missing environment variable: {name}")

    return value


TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", required=True)
TG_CHAT_ID = get_env("TG_CHAT_ID", required=True)
PORTFOLIO_JSON = get_env("PORTFOLIO_JSON", "portfolio.json")

REPORT_MODE = get_env("REPORT_MODE", "daily")

CHIP_TICKERS = {"AMD", "NVDA", "INTC", "AMAT", "TSM", "AVGO", "MU", "QCOM"}
DAYS_HISTORY = 30
BENCHMARK_TICKER = "VOO"