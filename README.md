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
## 🏗️ Architecture

- **Data Layer** — Fetches market data via APIs  
- **Processing Layer** — Calculates portfolio metrics (P&L, trends)  
- **Reporting Layer** — Generates summaries and charts  
- **Delivery Layer** — Sends reports via Telegram  
- **Automation Layer** — Schedules execution using GitHub Actions  

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


---

## 🔄 Execution Flow

1. Load portfolio configuration  
2. Fetch market data (prices + history)  
3. Calculate daily / weekly metrics  
4. Generate chart and summary  
5. Send report via Telegram  
6. Run automatically via GitHub Actions  

---

## 🧪 Validation & Reliability

- Handles missing or incomplete market data  
- Validates input portfolio structure  
- Uses safe calculations to avoid runtime errors  
- Separates logic into modular components for testability  

---

## 🔐 Security

Sensitive data is managed using environment variables and GitHub Secrets:

- No API keys or tokens are stored in the repository  
- Portfolio data is injected securely during runtime  

---

## 🤖 AI-Assisted Development

This project leverages AI tools (LLMs) to:

- Accelerate development  
- Improve code quality  
- Assist in debugging and system design  
