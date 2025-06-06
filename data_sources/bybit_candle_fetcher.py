# data_sources/bybit_candle_fetcher.py
import os
import time
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import pandas as pd

# Asumsi: Anda memiliki utilitas logger di utils/logger.py
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging.")

load_dotenv()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

# Inisialisasi sesi HTTP Bybit secara global di modul ini
try:
    session = HTTP(
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    logger.info("Bybit HTTP session initialized.")
except Exception as e:
    logger.critical(f"Failed to initialize Bybit HTTP session: {e}")
    session = None # Pastikan session adalah None jika gagal

def _convert_to_dataframe(data):
    """
    Mengonversi data candlestick Bybit (list of lists) ke Pandas DataFrame.
    """
    if not data:
        return pd.DataFrame()

    # Urutan data dari Bybit: [timestamp, open, high, low, close, volume, turnOver]
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])

    # Konversi tipe data
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
    df['open'] = pd.to_numeric(df['open'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    df['close'] = pd.to_numeric(df['close'])
    df['volume'] = pd.to_numeric(df['volume'])
    df['turnover'] = pd.to_numeric(df['turnover'])

    # Mengurutkan berdasarkan timestamp (API Bybit mengembalikan yang terbaru lebih dulu)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    return df

def fetch_bybit_candles(
    symbol: str = "SOLUSDT",
    interval: str = "15", # '1', '3', '5', '15', '30', '60', '120', '240', '360', '720', 'D', 'W', 'M'
    limit: int = 200, # Maksimal 1000
    start_time_ms: int = None, # Unix timestamp dalam milidetik
    end_time_ms: int = None,   # Unix timestamp dalam milidetik
    max_retries: int = 3,
    retry_delay: int = 5 # Detik
) -> pd.DataFrame:
    """
    Mengambil data candlestick dari Bybit.

    Args:
        symbol (str): Simbol trading (misalnya, "SOLUSDT").
        interval (str): Interval candlestick (misalnya, "15" untuk 15 menit).
        limit (int): Jumlah candlestick yang akan diambil. Maksimal 1000 per permintaan.
        start_time_ms (int, optional): Waktu mulai Unix timestamp dalam milidetik.
                                       Jika diberikan, 'limit' akan diabaikan untuk pengambilan historis.
        end_time_ms (int, optional): Waktu akhir Unix timestamp dalam milidetik.
                                     Default: waktu saat ini.
        max_retries (int): Jumlah percobaan ulang jika terjadi kegagalan.
        retry_delay (int): Penundaan (dalam detik) antar percobaan ulang.

    Returns:
        pd.DataFrame: DataFrame berisi data candlestick dengan kolom standar (timestamp, open, high, low, close, volume).
                      Mengembalikan DataFrame kosong jika ada kegagalan.
    """
    # Pastikan 'session' sudah diinisialisasi
    global session # Pastikan kita merujuk ke variabel global
    if session is None:
        logger.error("Bybit HTTP session is not initialized. Cannot fetch candles.")
        return pd.DataFrame()

    all_candles = []
    current_end_time = end_time_ms if end_time_ms is not None else int(datetime.now().timestamp() * 1000)

    # Menangani pengambilan data historis menggunakan start_time_ms dan end_time_ms
    if start_time_ms is not None:
        logger.info(f"Fetching historical Bybit candles for {symbol} ({interval}) from {datetime.fromtimestamp(start_time_ms / 1000)} to {datetime.fromtimestamp(current_end_time / 1000)}")
        
        while current_end_time > start_time_ms:
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": min(limit, 1000), # Batasi permintaan per panggilan ke 1000
                "endTime": current_end_time
            }
            
            for attempt in range(max_retries):
                try:
                    response = session.get_kline(**params)
                    if response['retCode'] == 0:
                        fetched_list = response['result']['list']
                        if not fetched_list:
                            logger.info(f"No more historical data for {symbol} at {datetime.fromtimestamp(current_end_time / 1000)}")
                            current_end_time = 0 # Hentikan loop
                            break # Keluar dari loop percobaan ulang
                        
                        # Data dari Bybit berurutan dari yang terbaru ke terlama
                        all_candles.extend(fetched_list)
                        
                        # Perbarui current_end_time ke timestamp lilin tertua yang baru diambil
                        # Tambahkan 1ms untuk menghindari tumpang tindih
                        current_end_time = int(fetched_list[-1][0]) - 1
                        logger.debug(f"Fetched {len(fetched_list)} candles. New current_end_time: {datetime.fromtimestamp(current_end_time / 1000)}")
                        
                        # Berhenti jika kita sudah mencapai atau melewati start_time_ms
                        if current_end_time <= start_time_ms:
                            logger.info(f"Reached or passed start_time for {symbol}.")
                            current_end_time = 0 # Hentikan loop utama
                            break # Keluar dari loop percobaan ulang
                            
                        time.sleep(1) # Jeda untuk menghindari rate limit saat mengambil data historis
                        break # Keluar dari loop percobaan ulang jika berhasil
                    else:
                        error_msg = response.get('retMsg', 'Unknown error')
                        logger.warning(f"Bybit API error (attempt {attempt+1}/{max_retries}) for {symbol}: {error_msg}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                except Exception as e:
                    logger.error(f"Network or unexpected error (attempt {attempt+1}/{max_retries}) fetching Bybit candles for {symbol}: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
            else:
                logger.error(f"Failed to fetch Bybit candles for {symbol} after {max_retries} attempts.")
                current_end_time = 0 # Hentikan loop jika semua percobaan gagal
    else:
        # Pengambilan data menggunakan 'limit' (default behavior)
        logger.info(f"Fetching latest {limit} Bybit candles for {symbol} ({interval}).")
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        for attempt in range(max_retries):
            try:
                response = session.get_kline(**params)
                if response['retCode'] == 0:
                    all_candles = response['result']['list']
                    logger.info(f"Successfully fetched {len(all_candles)} latest candles for {symbol}.")
                    break
                else:
                    error_msg = response.get('retMsg', 'Unknown error')
                    logger.warning(f"Bybit API error (attempt {attempt+1}/{max_retries}) for {symbol}: {error_msg}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Network or unexpected error (attempt {attempt+1}/{max_retries}) fetching Bybit candles for {symbol}: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        else:
            logger.error(f"Failed to fetch Bybit candles for {symbol} after {max_retries} attempts.")
            return pd.DataFrame() # Return kosong jika gagal

    # Konversi dan kembalikan data
    return _convert_to_dataframe(all_candles)

# --- Contoh Penggunaan (untuk pengujian) ---
if __name__ == "__main__":
    logger.info("Starting Bybit candle fetcher test...")

    # Contoh 1: Ambil 100 lilin terbaru untuk SOLUSDT pada interval 15 menit
    print("\n--- Contoh 1: 100 lilin terbaru SOLUSDT 15m ---")
    candles_latest = fetch_bybit_candles(symbol="SOLUSDT", interval="15", limit=100)
    if not candles_latest.empty:
        print(candles_latest.head())
        print(f"Total candles fetched: {len(candles_latest)}")
    else:
        print("Failed to fetch latest candles.")

    # Contoh 2: Ambil data historis untuk BTCUSDT, 1 jam, selama 2 hari terakhir
    print("\n--- Contoh 2: Data historis BTCUSDT 1h (2 hari terakhir) ---")
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=2)).timestamp() * 1000)
    
    candles_historical = fetch_bybit_candles(
        symbol="BTCUSDT",
        interval="60", # 1 jam
        start_time_ms=start_ts,
        end_time_ms=end_ts,
        limit=1000 # Maksimal limit per panggilan, akan diulang otomatis
    )
    if not candles_historical.empty:
        print(candles_historical.head())
        print(candles_historical.tail())
        print(f"Total historical candles fetched: {len(candles_historical)}")
    else:
        print("Failed to fetch historical candles.")
        
    # Contoh 3: Simbol yang tidak valid
    print("\n--- Contoh 3: Simbol tidak valid ---")
    candles_invalid = fetch_bybit_candles(symbol="XYZABC", interval="15", limit=10)
    if candles_invalid.empty:
        print("As expected, failed to fetch candles for invalid symbol XYZABC.")
    else:
        print("Unexpectedly fetched candles for invalid symbol XYZABC.")

    logger.info("Bybit candle fetcher test finished.")
