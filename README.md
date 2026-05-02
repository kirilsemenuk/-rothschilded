# Portfolio Telegram Bot

Automated portfolio tracking bot that analyzes stock performance and sends portfolio summaries to Telegram.

---

## Overview

This project tracks a stock portfolio using market data from Yahoo Finance, calculates portfolio performance, generates charts, and sends automated updates to Telegram.

The project is structured as a production-style Python application with separated modules for data fetching, portfolio calculations, report generation, and Telegram delivery.

---

## Features

- Fetches stock market data using `yfinance`
- Calculates portfolio value, daily change, profit/loss, and percentage returns
- Generates portfolio performance chart with Matplotlib
- Sends Telegram message and chart automatically
- Supports scheduled execution using GitHub Actions
- Handles runtime errors and sends error notifications to Telegram
- Keeps sensitive portfolio data outside the repository

---

## Project Structure

```text
portfolio-telegram-bot/
├── main.py
├── config.py
├── data_fetcher.py
├── portfolio_loader.py
├── portfolio_service.py
├── report_generator.py
├── telegram_client.py
├── utils.py
├── portfolio.example.json
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── portfolio-daily-report.yml
```

---

## Required Secrets

Add these repository secrets in GitHub:

```text
TELEGRAM_BOT_TOKEN
TG_CHAT_ID
PORTFOLIO_JSON_DATA
```

---

## Portfolio Example

Create a local `portfolio.json` file based on `portfolio.example.json`:

```json
[
  {
    "ticker": "AMD",
    "shares": 10,
    "avg_price": 120
  }
]
```

---

## How to Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Set environment variables:

```bash
set TELEGRAM_BOT_TOKEN=your_token
set TG_CHAT_ID=your_chat_id
set PORTFOLIO_JSON=portfolio.json
```

Run:

```bash
python main.py
```

---

## GitHub Actions

The workflow creates `portfolio.json` from a GitHub Secret and runs the bot automatically.

---

## Key Engineering Concepts

- API integration
- Financial data processing
- Automation workflows
- Error handling
- Modular Python architecture
- Scheduled execution
- Telegram Bot integration
- Data visualization

---
## 🖥️ Example Output

### 📅 Daily Report

![Daily Report](daily-report.png)

The bot sends a detailed daily summary including:

* Portfolio value and total P&L
* Daily performance and percentage change
* Top gainers and losers
* Market breadth analysis
* Smart insights based on portfolio behavior
* 30-day performance chart


## Author

Kiril Semeneuk  
GitHub: https://github.com/kirilsemenuk
