# utils/config_loader.py
import os
from dotenv import load_dotenv
import logging

# Asumsi: Anda memiliki utilitas logger di utils/logger.py
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging for config_loader.")

class ConfigLoader:
    """
    Kelas untuk memuat dan menyediakan akses terstruktur ke variabel lingkungan.
    Variabel dimuat dari file .env.
    """
    _instance = None # Pola Singleton untuk memastikan hanya ada satu instance ConfigLoader

    def __new__(cls, *args, **kwargs):
        """
        Menerapkan pola Singleton. Hanya satu instance ConfigLoader yang akan dibuat.
        """
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._initialized = False # Gunakan flag untuk inisialisasi satu kali
        return cls._instance

    def __init__(self):
        if self._initialized:
            return # Hindari re-inisialisasi jika sudah pernah dipanggil
        
        load_dotenv() # Muat variabel dari .env
        logger.info("Environment variables loaded from .env file.")

        self._config = {
            # EXCHANGE KEYS
            "BINANCE_API_KEY": os.getenv("BINANCE_API_KEY"),
            "BINANCE_SECRET_KEY": os.getenv("BINANCE_SECRET_KEY"),
            "BYBIT_API_KEY": os.getenv("BYBIT_API_KEY"), # Tambahkan Bybit jika ada
            "BYBIT_SECRET_KEY": os.getenv("BYBIT_SECRET_KEY"), # Tambahkan Bybit jika ada
            "OKX_API_KEY": os.getenv("OKX_API_KEY"),
            "OKX_SECRET_KEY": os.getenv("OKX_SECRET_KEY"),

            # RPC (Remote Procedure Call - untuk blockchain seperti Solana)
            "SOLANA_RPC_URL": os.getenv("SOLANA_RPC_URL"),

            # INFLUXDB (Database Time-Series)
            "INFLUXDB_HOST": os.getenv("INFLUXDB_HOST"),
            "INFLUXDB_PORT": os.getenv("INFLUXDB_PORT"),
            "INFLUXDB_TOKEN": os.getenv("INFLUXDB_TOKEN"),
            "INFLUXDB_ORG": os.getenv("INFLUXDB_ORG"),
            "INFLUXDB_BUCKET": os.getenv("INFLUXDB_BUCKET"),

            # REDIS (Database In-Memory, untuk caching atau pub/sub)
            "REDIS_HOST": os.getenv("REDIS_HOST"),
            "REDIS_PORT": os.getenv("REDIS_PORT"),
            "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD"),

            # TELEGRAM (Untuk notifikasi sinyal)
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),

            # Tambahkan konfigurasi umum lainnya di sini jika diperlukan
            "DEFAULT_CANDLE_LIMIT": int(os.getenv("DEFAULT_CANDLE_LIMIT", "500")),
            "ANALYSIS_INTERVALS": os.getenv("ANALYSIS_INTERVALS", "1h,4h,1d").split(',')
        }
        
        self._validate_config()
        self._initialized = True
        logger.info("Configuration loaded and validated.")

    def _validate_config(self):
        """
        Memvalidasi keberadaan kunci-kunci konfigurasi yang penting.
        Akan mencatat peringatan atau error jika kunci penting tidak ditemukan.
        """
        required_keys = [
            "BINANCE_API_KEY", "BINANCE_SECRET_KEY",
            "BYBIT_API_KEY", "BYBIT_SECRET_KEY", # Pastikan ini diisi
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
        ]
        
        missing_keys = [key for key in required_keys if not self._config.get(key)]

        if missing_keys:
            logger.warning(f"Warning: Missing essential configuration keys in .env: {', '.join(missing_keys)}")
            logger.warning("Some functionalities might not work correctly without these keys.")
        else:
            logger.info("All essential configuration keys found.")

        # Contoh validasi untuk InfluxDB atau Redis jika perlu
        if self._config.get("INFLUXDB_HOST") and not all([self._config.get(k) for k in ["INFLUXDB_PORT", "INFLUXDB_TOKEN", "INFLUXDB_ORG", "INFLUXDB_BUCKET"]]):
            logger.warning("InfluxDB host is set, but other InfluxDB connection details are missing.")
        
        if self._config.get("REDIS_HOST") and not self._config.get("REDIS_PORT"):
             logger.warning("Redis host is set, but Redis port is missing.")


    def get(self, key: str, default=None):
        """
        Mendapatkan nilai konfigurasi berdasarkan kunci.
        
        Args:
            key (str): Nama kunci konfigurasi (misal, "BINANCE_API_KEY").
            default: Nilai default yang akan dikembalikan jika kunci tidak ditemukan.
        
        Returns:
            str/int/None: Nilai konfigurasi atau nilai default.
        """
        value = self._config.get(key, default)
        if value is None and default is None:
            logger.debug(f"Configuration key '{key}' not found and no default provided.")
        return value

    def load_config(self):
        """
        Mengembalikan kamus konfigurasi yang dimuat.
        """
        return self._config

# --- Contoh Penggunaan (untuk pengujian) ---
if __name__ == "__main__":
    logger.info("Memulai pengujian ConfigLoader...")

    # Pastikan Anda memiliki file .env di root proyek Anda
    # dengan contoh variabel seperti:
    # BINANCE_API_KEY=your_key
    # BINANCE_SECRET_KEY=your_secret
    # TELEGRAM_BOT_TOKEN=your_token
    # TELEGRAM_CHAT_ID=your_chat_id
    # DEFAULT_CANDLE_LIMIT=1000
    # ANALYSIS_INTERVALS=1m,5m,15m,1h

    config = ConfigLoader() # Instance pertama akan memuat config
    
    # Ambil nilai konfigurasi
    binance_key = config.get("BINANCE_API_KEY")
    telegram_token = config.get("TELEGRAM_BOT_TOKEN")
    solana_rpc = config.get("SOLANA_RPC_URL", "http://localhost:8899")
    default_limit = config.get("DEFAULT_CANDLE_LIMIT")
    analysis_intervals = config.get("ANALYSIS_INTERVALS")
    
    logger.info(f"Binance API Key (first 5 chars): {binance_key[:5] if binance_key else 'N/A'}")
    logger.info(f"Telegram Bot Token (first 5 chars): {telegram_token[:5] if telegram_token else 'N/A'}")
    logger.info(f"Solana RPC URL: {solana_rpc}")
    logger.info(f"Default Candle Limit: {default_limit}")
    logger.info(f"Analysis Intervals: {analysis_intervals}")

    # Uji akses instance kedua (seharusnya sama karena Singleton)
    another_config_instance = ConfigLoader()
    logger.info(f"Is it the same instance? {config is another_config_instance}")

    # Uji kunci yang hilang
    missing_key_value = config.get("NON_EXISTENT_KEY", "default_value_for_missing")
    logger.info(f"Non-existent key value: {missing_key_value}")

    logger.info("Pengujian ConfigLoader selesai.")
