import os
import logging
from datetime import datetime, timezone

import yfinance as yf
import pandas as pd
from azure.storage.blob import BlobServiceClient
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TICKERS  = os.getenv("TICKERS", "NESN.SW,NOVN.SW,ROG.SW,UHR.SW,ABBN.SW").split(",")
PERIOD   = os.getenv("PERIOD", "30d")
INTERVAL = os.getenv("INTERVAL", "1d")

BLOB_CONN_STR  = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER", "raw-prices")

PG_HOST = os.environ["PG_HOST"]
PG_DB   = os.environ["PG_DATABASE"]
PG_USER = os.environ["PG_USER"]
PG_PW   = os.environ["PG_PASSWORD"]


def fetch_prices(tickers, period, interval):
    log.info("Fetching %d tickers", len(tickers))
    raw = yf.download(tickers, period=period, interval=interval, auto_adjust=True, progress=False)
    close = raw["Close"] if len(tickers) > 1 else raw[["Close"]]
    if len(tickers) == 1:
        close.columns = tickers
    df = close.stack(future_stack=True).reset_index()
    df.columns = ["date", "ticker", "close"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["fetched_at"] = datetime.now(timezone.utc)
    df = df.dropna(subset=["close"])
    log.info("Fetched %d rows", len(df))
    return df


def upload_to_blob(df, container, conn_str):
    blob_name = f"prices/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    client = BlobServiceClient.from_connection_string(conn_str)
    container_client = client.get_container_client(container)
    try:
        container_client.create_container()
        log.info("Created container '%s'", container)
    except Exception:
        pass
    container_client.upload_blob(name=blob_name, data=csv_bytes, overwrite=True)
    log.info("Uploaded blob: %s", blob_name)


def load_to_postgres(df, host, database, user, password):
    conn = psycopg2.connect(
        host=host, dbname=database, user=user, password=password, sslmode="require"
    )
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id         SERIAL PRIMARY KEY,
                    date       DATE         NOT NULL,
                    ticker     VARCHAR(20)  NOT NULL,
                    close      FLOAT        NOT NULL,
                    fetched_at TIMESTAMP    NOT NULL,
                    CONSTRAINT uq_date_ticker UNIQUE (date, ticker)
                );
            """)
            rows = list(df[["date", "ticker", "close", "fetched_at"]].itertuples(index=False, name=None))
            cur.executemany("""
                INSERT INTO stock_prices (date, ticker, close, fetched_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (date, ticker)
                DO UPDATE SET close = EXCLUDED.close, fetched_at = EXCLUDED.fetched_at;
            """, rows)
            log.info("Upserted %d rows into stock_prices", len(rows))
    conn.close()


def main():
    df = fetch_prices(TICKERS, PERIOD, INTERVAL)
    upload_to_blob(df, BLOB_CONTAINER, BLOB_CONN_STR)
    try:
        load_to_postgres(df, PG_HOST, PG_DB, PG_USER, PG_PW)
    except Exception as e:
        log.warning("Postgres not available, skipping: %s", e)
    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
