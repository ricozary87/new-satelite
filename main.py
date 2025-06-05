import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import time
import os
from dotenv import load_dotenv
import logging

# --- Impor semua modul yang diperlukan dari project Anda ---
# Pastikan jalur impor sesuai dengan struktur direktori Anda.
from data_sources.binance_candle_fetcher import BinanceCandleFetcher
from analyzers.classic_indicators import calculate_indicators
from analyzers.smc_structure import analyze_smc_structure
from logic_engine.signal_builder import generate_trading_signal
from outputs.telegram_messenger import TelegramMessenger
from utils.config_loader import load_config
from utils.logger import setup_logger

# >>> Tambahkan impor untuk fungsionalitas analisis manual <<<
# Ini adalah impor baru yang Anda minta
from core.analyzer_entry import analyze_coin as manual_analyze_coin # Memberi alias agar tidak bentrok dengan fungsi lain

# Muat environment variables dari file .env di awal skrip
load_dotenv()

# --- Setup Logging ---
logger = setup_logger(__name__, log_level=logging.INFO, log_file="trading_bot.log")

# --- Konfigurasi ---
try:
    config = load_config()
except Exception as e:
    logger.warning(f"Tidak dapat memuat konfigurasi dari config_loader.py: {e}. Menggunakan variabel lingkungan langsung.")
    config = {}

SYMBOL = config.get("SYMBOL", os.getenv("SYMBOL", "BTCUSDT"))
TIMEFRAME = config.get("TIMEFRAME", os.getenv("TIMEFRAME", "5m"))
LIMIT_CANDLES = config.get("LIMIT_CANDLES", int(os.getenv("LIMIT_CANDLES", 300)))
RUN_INTERVAL_SECONDS = config.get("RUN_INTERVAL_SECONDS", int(os.getenv("RUN_INTERVAL_SECONDS", 300)))

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Inisialisasi Fetcher dan Messenger
# UNCOMMENT baris ini dan pastikan konfigurasi API Keys/Token Anda benar untuk produksi.
# fetcher = BinanceCandleFetcher(api_key=BINANCE_API_KEY, secret_key=BINANCE_SECRET_KEY)
messenger = TelegramMessenger(bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID)


def get_timeframe_interval_seconds(timeframe: str) -> int:
    """Mengubah timeframe string (e.g., '5m', '1h') menjadi detik."""
    if timeframe.endswith('m'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 3600
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 86400
    logger.warning(f"Timeframe tidak dikenal: {timeframe}. Menggunakan interval default 300 detik (5 menit).")
    return 300


def simulate_data_fetch(num_candles: int, timeframe: str) -> pd.DataFrame:
    """
    Fungsi simulasi untuk mengambil data OHLCV.
    Dalam produksi, ini akan diganti dengan fetcher asli Anda (e.g., BinanceCandleFetcher).
    Ditambahkan parameter timeframe untuk simulasi interval yang lebih akurat.
    """
    logger.info(f"Mengambil {num_candles} candle data simulasi...")
    
    interval_seconds = get_timeframe_interval_seconds(timeframe) # Gunakan timeframe dari parameter
    interval_minutes = interval_seconds // 60
    
    start_time = datetime.now() - timedelta(minutes=num_candles * interval_minutes)

    prices = np.linspace(100, 200, num_candles) + np.random.normal(0, 5, num_candles)
    
    opens = np.roll(prices, 1)
    highs = np.maximum(prices * 1.005, prices * 1.001 + np.random.uniform(0, 1, num_candles))
    lows = np.minimum(prices * 0.995, prices * 0.999 - np.random.uniform(0, 1, num_candles))
    closes = prices

    df = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes,
        'volume': [1000 + i * 10 + np.random.randint(-200, 200) for i in range(num_candles)]
    }, index=pd.to_datetime([start_time + timedelta(minutes=i * interval_minutes) for i in range(num_candles)]))
    
    df.columns = ['open', 'high', 'low', 'close', 'volume']
    
    logger.info("Data simulasi berhasil dibuat.")
    return df

def run_automated_analysis_and_signal_generation():
    """
    Menjalankan seluruh alur analisis dan pembangkitan sinyal untuk
    symbol dan timeframe yang dikonfigurasi secara otomatis.
    """
    logger.info(f"\n--- Memulai Analisis Otomatis untuk {SYMBOL} di Timeframe {TIMEFRAME} ---")

    # 1. Ambil Data OHLCV
    try:
        # Untuk produksi, uncomment baris ini dan pastikan 'fetcher' sudah diinisialisasi
        # df = fetcher.fetch_candles(SYMBOL, TIMEFRAME, limit=LIMIT_CANDLES)
        
        # Untuk pengembangan/pengujian, gunakan data simulasi:
        df = simulate_data_fetch(num_candles=LIMIT_CANDLES, timeframe=TIMEFRAME) # Kirim TIMEFRAME ke simulasi
        
        if df.empty:
            logger.error("❌ Data kosong, tidak bisa melanjutkan analisa.")
            return
    except Exception as e:
        logger.error(f"❌ Error saat mengambil data candle: {e}", exc_info=True)
        return

    current_price = df['close'].iloc[-1]
    current_open_price = df['open'].iloc[-1]

    logger.info(f"Harga Penutupan Terakhir: {current_price:.4f}, Harga Pembukaan Terakhir: {current_open_price:.4f}")

    # 2. Hitung Indikator Klasik
    logger.info("\n--- Menghitung Indikator Klasik ---")
    classic_indicators_results = calculate_indicators(df.copy())
    if classic_indicators_results:
        for key, value in classic_indicators_results.items():
            if isinstance(value, (float, int)):
                logger.info(f"  {key}: {value:.4f}")
            else:
                logger.info(f"  {key}: {value}")
    else:
        logger.error("❌ Gagal menghitung indikator klasik. Menghentikan proses.")
        return

    # 3. Analisis Struktur SMC
    logger.info("\n--- Menganalisis Struktur SMC ---")
    smc_analysis_results = analyze_smc_structure(df.copy())
    if smc_analysis_results:
        for key, value in smc_analysis_results.items():
            if isinstance(value, (dict, list)) and key not in ['reason', 'swing_points']:
                logger.info(f"  {key}: {value}")
            elif key == 'swing_points':
                logger.info(f"  {key}: {len(value.get('swing_highs', []))} Swing Highs, {len(value.get('swing_lows', []))} Swing Lows")
            else:
                logger.info(f"  {key}: {value}")
    else:
        logger.error("❌ Gagal menganalisis struktur SMC. Menghentikan proses.")
        return

    # 4. Bangun Sinyal Trading
    logger.info("\n--- Membangun Sinyal Trading ---")
    if classic_indicators_results and smc_analysis_results and current_price is not None and current_open_price is not None:
        trading_signal = generate_trading_signal(
            symbol=SYMBOL, # Menggunakan SYMBOL yang dikonfigurasi
            timeframe=TIMEFRAME, # Menggunakan TIMEFRAME yang dikonfigurasi
            classic_indicators=classic_indicators_results,
            smc_signals=smc_analysis_results,
            df=df,
            current_price=current_price,
            current_open_price=current_open_price
        )
        logger.info("\n--- Sinyal Trading Dihasilkan ---")
        for key, value in trading_signal.items():
            logger.info(f"  {key}: {value}")

        # 5. Kirim Notifikasi (Opsional)
        if trading_signal['signal'] != 'NO_SIGNAL':
            msg = (
                f"🚨 <b>Sinyal Trading {trading_signal['signal']}</b> ({trading_signal['strength'].replace('_', ' ').title()}) 🚨\n"
                f"Symbol: {trading_signal['symbol']}\n"
                f"Timeframe: {trading_signal['timeframe']}\n"
                f"Entry Price: {trading_signal['entry_price']:.4f}\n"
                f"Stop Loss: {trading_signal['stop_loss']:.4f}\n"
                f"Take Profit 1: {trading_signal['take_profit_1']:.4f}\n"
                f"Take Profit 2: {trading_signal['take_profit_2']:.4f}\n"
                f"Take Profit 3: {trading_signal['take_profit_3']:.4f}\n"
                f"Base RRR: {trading_signal['risk_reward_ratio_base']}\n"
                f"Reason: {trading_signal['reason']}"
            )
            try:
                # messenger.send_message(msg)
                logger.info("Sinyal berhasil dikirim ke Telegram (mode simulasi/dinonaktifkan).")
            except Exception as e:
                logger.error(f"❌ Gagal mengirim sinyal ke Telegram: {e}", exc_info=True)
        else:
            logger.info("⚠️ Tidak ada sinyal trading yang dihasilkan pada saat ini.")
            
    else:
        logger.error("❌ Data tidak lengkap untuk menghasilkan sinyal trading. Menghentikan proses.")
    logger.info(f"--- Analisis Otomatis untuk {SYMBOL} Selesai ---\n")


# --- Jalankan program utama ---
if __name__ == "__main__":
    # --- Mode Manual (untuk pengujian atau analisis satu kali) ---
    # Ini akan memanggil analyze_coin dari core.analyzer_entry.py
    # Baris di bawah ini akan dijalankan HANYA jika Anda menjalankan main.py secara langsung
    # dan jika Anda TIDAK ingin bot berjalan dalam loop otomatis.
    # Untuk menjalankan secara manual, Anda bisa un-comment baris di bawah ini
    # dan me-remark (atau menghapus) bagian automated_analysis_loop.
    
    # manual_analyze_coin("BTCUSDT", "5m") # Contoh: analisis BTCUSDT di timeframe 5 menit
    # manual_analyze_coin("ETHUSDT", "1h") # Contoh lain: analisis ETHUSDT di timeframe 1 jam
    
    # >>> Pilih salah satu dari mode di bawah ini: <<<
    # 1. Jika Anda ingin menjalankan loop otomatis, un-comment yang ini:
    try:
        logger.info("Memulai bot trading dalam mode otomatis...")
        while True:
            run_automated_analysis_and_signal_generation()
            interval = get_timeframe_interval_seconds(TIMEFRAME)
            logger.info(f"\nMenunggu {TIMEFRAME} ({interval} detik) untuk analisis otomatis berikutnya...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("🛑 Bot trading dihentikan oleh pengguna.")
    except Exception as e:
        logger.critical(f"❌ Terjadi kesalahan fatal pada bot: {e}", exc_info=True)


    # 2. Jika Anda hanya ingin menjalankan analisis manual, un-comment bagian manual_analyze_coin di atas
    #    dan pastikan bagian loop otomatis di atas di-remark (atau dihapus).
