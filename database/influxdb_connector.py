# database/influxdb_connector.py

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS # Tambahkan ini
from utils.config_loader import load_config
from utils.logger import setup_logger # Tambahkan ini

# Inisialisasi logger untuk modul ini
logger = setup_logger(__name__)

config = load_config()

# --- Konfigurasi InfluxDB ---
# Bentuk URL dari HOST dan PORT
INFLUXDB_URL = f"http://{config['INFLUXDB_HOST']}:{config['INFLUXDB_PORT']}"
INFLUXDB_TOKEN = config["INFLUXDB_TOKEN"]
INFLUXDB_ORG = config["INFLUXDB_ORG"]
INFLUXDB_BUCKET = config["INFLUXDB_BUCKET"]

# --- Inisialisasi Client InfluxDB ---
# Gunakan try-except untuk penanganan error koneksi awal
try:
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )
    # Ping client untuk memastikan koneksi berhasil
    client.ping()
    logger.info(f"Connected to InfluxDB at {INFLUXDB_URL} successfully.")
except Exception as e:
    logger.error(f"Failed to connect to InfluxDB at {INFLUXDB_URL}: {e}")
    # Anda bisa memilih untuk keluar dari aplikasi atau memberikan nilai None
    client = None
    write_api = None # Pastikan write_api juga None jika client gagal
    raise # Re-raise exception agar aplikasi tahu ada masalah fatal

# Inisialisasi Write API hanya jika client berhasil terhubung
if client:
    write_api = client.write_api(write_options=SYNCHRONOUS) # Gunakan SYNCHRONOUS untuk penulisan langsung
else:
    write_api = None

def write_to_influx(measurement: str, data: dict, tags: dict = None, bucket=None):
    """
    Menulis satu Point data ke InfluxDB.

    Args:
        measurement (str): Nama pengukuran (misal: "ohlcv", "trades").
        data (dict): Dictionary berisi fields dan timestamp.
                     Harus berisi 'timestamp' (Unix epoch di MS atau string ISO).
        tags (dict, optional): Dictionary berisi tags. Default is None.
        bucket (str, optional): Nama bucket yang akan digunakan. Jika None, menggunakan default dari config.
    """
    if not write_api:
        logger.error("InfluxDB write_api is not initialized. Cannot write data.")
        return

    # Pastikan tags adalah dictionary jika None
    if tags is None:
        tags = {}

    point = Point(measurement)

    # Tambahkan tags
    for key, value in tags.items():
        point.tag(key, value)

    # Tambahkan fields
    for key, value in data.items():
        if key != "timestamp": # 'timestamp' akan ditangani secara terpisah
            point.field(key, value)
    
    # Tambahkan timestamp. Pastikan data['timestamp'] ada.
    if "timestamp" in data:
        # Asumsi timestamp dari exchange adalah milidetik
        point.time(data["timestamp"], WritePrecision.MS)
    else:
        logger.warning(f"Data for measurement '{measurement}' is missing 'timestamp' field. Using current time.")
        # Jika timestamp tidak ada, gunakan waktu saat ini (kurang direkomendasikan untuk data historis)
        point.time(WritePrecision.NS) # Default nanosecond

    try:
        target_bucket = bucket or INFLUXDB_BUCKET # Gunakan bucket dari parameter atau default
        write_api.write(bucket=target_bucket, record=point)
        # logger.debug(f"Successfully wrote data to InfluxDB bucket '{target_bucket}' for measurement '{measurement}'.")
    except Exception as e:
        logger.error(f"Failed to write data to InfluxDB: {e}")

# Fungsi untuk menutup koneksi InfluxDB (penting saat aplikasi mati)
def close_influx_client():
    if client:
        client.close()
        logger.info("InfluxDB client closed.")

# Contoh penggunaan (untuk pengujian saja)
if __name__ == "__main__":
    test_logger = setup_logger("influx_test")
    test_logger.info("Starting InfluxDB connector test...")

    # Pastikan InfluxDB server berjalan dan konfigurasi di .env sudah benar
    # Contoh data OHLCV
    ohlcv_data = {
        "open": 100.0,
        "high": 105.0,
        "low": 99.0,
        "close": 104.5,
        "volume": 1000.0,
        "timestamp": 1678886400000 # Contoh Unix epoch in milliseconds
    }
    ohlcv_tags = {
        "symbol": "SOLUSDT",
        "interval": "1m",
        "exchange": "BINANCE"
    }

    # Contoh data trade
    trade_data = {
        "price": 104.5,
        "qty": 50.0,
        "is_buyer_maker": False, # False means seller is maker, or market sell
        "timestamp": 1678886401234
    }
    trade_tags = {
        "symbol": "SOLUSDT",
        "exchange": "OKX"
    }

    try:
        write_to_influx("ohlcv", ohlcv_data, ohlcv_tags)
        test_logger.info("OHLCV test data written.")

        write_to_influx("trades", trade_data, trade_tags)
        test_logger.info("Trade test data written.")

        # Menulis data tanpa timestamp
        # write_to_influx("test_no_ts", {"value": 10})
        # test_logger.info("Data without timestamp written (using current time).")

    except Exception as e:
        test_logger.error(f"Error during InfluxDB write test: {e}")
    finally:
        close_influx_client()
        test_logger.info("InfluxDB test finished and client closed.")
