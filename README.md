# 📊 Portfolio Analytics Telegram Bot

Automated portfolio analytics system that tracks stock performance and sends daily and weekly reports via Telegram.

---

## 🚀 Overview

This project implements an end-to-end portfolio monitoring pipeline:

* Retrieves real-time market data using financial APIs
* Calculates portfolio performance (P&L, daily & weekly changes)
* Generates visual reports (charts)
* Sends automated summaries via Telegram
* Runs on scheduled workflows using GitHub Actions

---

## 🧠 Why This Project Matters

This project demonstrates real-world engineering skills relevant to system validation and automation:

* Building automated data pipelines
* Designing modular systems
* Working with APIs and external data sources
* Debugging and validating system behavior
* Using AI-assisted tools to accelerate development

---

## 🏗️ System Architecture

```
Portfolio JSON
      ↓
Data Fetcher (APIs)
      ↓
Portfolio Service (Calculations)
      ↓
Report Generator (Charts + Summary)
      ↓
Telegram Client (Delivery)
      ↓
GitHub Actions (Automation)
```

---

## 🔧 Key Features

* Automated daily & weekly reporting
* Weekly calculation based on last 5 trading days
* Portfolio performance analytics (P&L, trends)
* Data visualization using Matplotlib
* Telegram bot integration
* GitHub Actions automation
* Modular and scalable architecture

---

## 🖥️ Example Output

### 📅 Daily Report

![Daily Report](daily-report.png)

### 📆 Weekly Report

![Weekly Report](weekly-report.png)

Reports include:

* Portfolio value and total P&L
* Daily / weekly performance
* Top gainers and losers
* Market breadth (advancers vs decliners)
* 30-day performance chart

---

## ▶️ How to Run Locally

```bash
pip install -r requirements.txt
python main.py
```

Set environment variables:

```bash
TELEGRAM_BOT_TOKEN=your_token
TG_CHAT_ID=your_chat_id
PORTFOLIO_JSON=portfolio.json
REPORT_MODE=daily   # or weekly
```

---

## ⚙️ Automation (GitHub Actions)

The system runs automatically using GitHub Actions:

* Daily reports (weekdays)
* Weekly summary

### Secrets used:

* `TELEGRAM_BOT_TOKEN`
* `TG_CHAT_ID`
* `PORTFOLIO_JSON_DATA`

---

## 🛠️ Technologies Used

* Python
* Yahoo Finance API (yfinance)
* Matplotlib
* GitHub Actions (CI/CD)
* Telegram Bot API

---

## 📈 Future Improvements

* Benchmark comparison (e.g. S&P 500)
* Advanced analytics (risk, volatility)
* Multi-portfolio support
* PDF / dashboard reporting
