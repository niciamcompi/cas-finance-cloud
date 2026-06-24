# CAS Finance Cloud – Swiss Stock Price Pipeline

Automated pipeline that fetches Swiss stock prices (SMI constituents) via Yahoo Finance,
stores raw CSV files in Azure Blob Storage, and upserts data into PostgreSQL.

## Architecture
- **Data source**: Yahoo Finance (yfinance)
- **Storage**: Azure Blob Storage (`raw-prices` container)
- **Database**: Azure PostgreSQL Flexible Server
- **Containerization**: Docker
- **CI/CD**: GitLab CI/CD (build + scheduled run)

## Tickers
NESN.SW, NOVN.SW, UHR.SW, ABBN.SW (ROG.SW currently delisted on Yahoo Finance)

## Setup

### Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
### Run locally with Docker
```bash
docker build -t price-pipeline .
docker run --env-file .env price-pipeline
```

## CI/CD
Pipeline runs automatically on push and on a daily schedule.
Secrets are stored as GitLab CI/CD Variables (masked).

## Author
Nicola Rothlin – CAS Data Engineering, FHNW 2026
