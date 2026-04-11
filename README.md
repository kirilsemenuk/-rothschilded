# -rothschilded
Weekly portfolio tracker with Telegram alerts
# Portfolio Telegram Bot

A Python automation project that generates weekly portfolio summaries and sends them to Telegram.

## What it does
- Loads holdings from `portfolio.json`
- Pulls market data with `yfinance`
- Calculates portfolio value, total P&L, and weekly change
- Compares performance against `VOO`
- Builds a 30-day portfolio chart
- Generates AI-style alerts for concentration, momentum, weakness, and benchmark performance
- Sends a formatted summary plus chart to Telegram

## Main file
- `bot_weekly.py`

## Required environment variables
- `TELEGRAM_BOT_TOKEN`
- `TG_CHAT_ID`
- `PORTFOLIO_JSON` (optional, defaults to `portfolio.json`)

## Example workflow
1. Read `portfolio.json`
2. Fetch historical prices
3. Build weekly metrics
4. Generate summary text and alerts
5. Create chart image
6. Send everything to Telegram

## Tech stack
- Python
- yfinance
- requests
- matplotlib
- GitHub Actions
- Telegram Bot API

## Why this project is good for interviews
It demonstrates practical Python development, API integration, automation, data transformation, visualization, and product thinking in one compact project.
