import os
import time
from datetime import datetime, timedelta
import pandas as pd
from binance.client import Client
from binance.enums import HistoricalKlinesType
from binance.exceptions import BinanceAPIException, BinanceRequestException

# Logger setup
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging.")

# Load environment variables from root .env
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

class BinanceCandleFetcher:
    def __init__(self):
        api_key = os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_SECRET_KEY")

        if not api_key or not secret_key:
            logger.critical("BINANCE_API_KEY or BINANCE_SECRET_KEY not found in environment variables.")
            self.client = None
        else:
            try:
                self.client = Client(api_key, secret_key)
                logger.info("Binance API client initialized successfully.")
            except Exception as e:
                logger.critical(f"Failed to initialize Binance API client: {e}")
                self.client = None

    def _process_klines(self, klines):
        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])

        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('open_time', inplace=True)
        return df[['open', 'high', 'low', 'close', 'volume']].sort_index()

    def fetch_candles(self, symbol, interval, start_str=None, end_str=None, limit=None,
                      klines_type=HistoricalKlinesType.SPOT, max_retries=5, retry_delay=5):

        if self.client is None:
            logger.error("Binance API client is not initialized. Cannot fetch candles.")
            return pd.DataFrame()

        for attempt in range(max_retries):
            try:
                if start_str:
                    logger.info(f"Fetching historical Binance candles for {symbol} ({interval}) from '{start_str}' to '{end_str or 'now'}'.")
                    klines = self.client.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_str=start_str,
                        end_str=end_str,
                        klines_type=klines_type
                    )
                else:
                    if not limit:
                        limit = 500
                    logger.info(f"Fetching latest {limit} Binance candles for {symbol} ({interval}).")
                    klines = self.client.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        limit=limit,
                        klines_type=klines_type
                    )

                if not klines:
                    logger.info(f"No klines data found for {symbol} on {interval}.")
                    return pd.DataFrame()

                logger.info(f"Fetched {len(klines)} candles for {symbol}.")
                return self._process_klines(klines)

            except BinanceAPIException as e:
                if e.code == -1003:
                    logger.warning(f"Rate limit hit (attempt {attempt+1}). Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                elif e.code == -1121:
                    logger.error(f"Invalid symbol: {symbol}.")
                    return pd.DataFrame()
                else:
                    logger.error(f"API error (attempt {attempt+1}): {e}. Retrying...")
                    time.sleep(retry_delay)
            except BinanceRequestException as e:
                logger.error(f"Request error (attempt {attempt+1}): {e}. Retrying...")
                time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt+1}): {e}. Retrying...")
                time.sleep(retry_delay)

        logger.error(f"Failed to fetch candles for {symbol} after {max_retries} attempts.")
        return pd.DataFrame()

# --- TEST BLOCK ---
if __name__ == "__main__":
    logger.info("Starting Binance candle fetcher test...")

    fetcher = BinanceCandleFetcher()

    if fetcher.client:
        print("\n--- Example 1: Latest 1h BTCUSDT candles ---")
        df1 = fetcher.fetch_candles("BTCUSDT", "1h", limit=500)
        print(df1.head())

        print("\n--- Example 2: Historical 4h ETHUSDT last 3 days ---")
        df2 = fetcher.fetch_candles("ETHUSDT", "4h", start_str="3 days ago", end_str="now")
        print(df2.head(), df2.tail())

        print("\n--- Example 3: Invalid symbol test ---")
        df3 = fetcher.fetch_candles("FAKESYMBOL", "1h", limit=10)
        if df3.empty:
            print("✅ Invalid symbol handled correctly.")

    logger.info("Binance candle fetcher test finished.")
