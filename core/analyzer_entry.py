# core/analyzer_entry.py
import sys
import os
import logging
import numpy as np
import pandas as pd
import asyncio # Tambahkan ini untuk mendukung fungsi asinkron
from datetime import datetime, timedelta

# Tambahkan direktori root proyek ke sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Impor modul logging kustom
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging.")

# Impor modul konfigurasi
try:
    from utils.config_loader import ConfigLoader
except ImportError:
    logger.critical("Error: utils/config_loader.py not found. Please ensure it exists.")
    ConfigLoader = None

# Impor data fetcher Binance (ini adalah kelas)
from data_sources.binance_candle_fetcher import BinanceCandleFetcher

# Impor fungsi fetch_bybit_candles secara langsung
# Dan impor modul bybit_candle_fetcher itu sendiri untuk mengakses variabel global seperti 'session'
from data_sources.bybit_candle_fetcher import fetch_bybit_candles
import data_sources.bybit_candle_fetcher as bybit_fetcher_module

# Impor modul-modul analisis dan logika
from analyzers.classic_indicators import calculate_indicators
from analyzers.smc_structure import analyze_smc_structure
from logic_engine.confluence_checker import evaluate_confluence
from logic_engine.signal_builder import generate_trading_signal
from outputs.telegram_messenger import send_signal_to_telegram
from outputs.gpt_summarizer import get_gpt_analysis # get_gpt_analysis adalah fungsi async

class AnalyzerEntry:
    """
    Kelas ini bertindak sebagai titik masuk utama untuk alur kerja analisis.
    Ini mengelola pengambilan data, analisis, evaluasi logika, dan pengiriman sinyal.
    """
    def __init__(self):
        # Inisialisasi pengelola konfigurasi
        if ConfigLoader is None:
            logger.critical("ConfigLoader not available. Exiting AnalyzerEntry initialization.")
            self.config = None
            self.binance_fetcher = None
            return

        self.config = ConfigLoader().load_config() # Asumsi load_config() mengembalikan dict/obj konfigurasi

        # Inisialisasi data fetcher Binance
        self.binance_fetcher = BinanceCandleFetcher()

        # Untuk Bybit, kita tidak perlu membuat instance karena fetcher-nya adalah fungsi
        # Kita hanya perlu memeriksa apakah sesi Bybit diinisialisasi di modulnya sendiri.
        if bybit_fetcher_module.session is None: # Periksa apakah sesi Bybit berhasil diinisialisasi
             logger.warning("Bybit fetcher session not initialized in its module. Bybit data fetching will not work.")

        logger.info("AnalyzerEntry initialized with data fetchers.")

    # >>>>>> PERBAIKAN PENTING: analyze_coin sekarang adalah fungsi asinkron <<<<<<
    async def analyze_coin(self, symbol: str, timeframe: str = "1h", candle_limit: int = 300, exchange: str = "binance"):
        """
        Menganalisis data OHLCV untuk pasangan koin tertentu dari bursa yang ditentukan,
        menghitung indikator, menganalisis struktur pasar, mengevaluasi konfluensi,
        membangun sinyal, dan mengirimkannya jika valid.

        Args:
            symbol (str): Simbol pasangan koin (misalnya, "BTCUSDT").
            timeframe (str): Timeframe candle (misalnya, "1h", "4h").
            candle_limit (int): Jumlah candle data yang akan diambil.
            exchange (str): Bursa untuk mengambil data ('binance' atau 'bybit').
        """
        logger.info(f"\n--- Memulai Analisis untuk {symbol} di {exchange.upper()} Timeframe {timeframe} ---")

        df = pd.DataFrame() # Inisialisasi DataFrame kosong

        try:
            # --- Pengambilan Data OHLCV dari Bursa ---
            logger.info(f"Mengambil {candle_limit} candle data dari {exchange.upper()}...")
            
            if exchange.lower() == "binance":
                if not self.binance_fetcher.client:
                    logger.error("Binance fetcher not available or not initialized.")
                    return # Keluar jika fetcher tidak siap
                
                df = self.binance_fetcher.fetch_candles(
                    symbol=symbol,
                    interval=timeframe,
                    limit=candle_limit
                )
            elif exchange.lower() == "bybit":
                if bybit_fetcher_module.session is None: # Periksa sesi Bybit global
                    logger.error("Bybit fetcher session is not available. Cannot fetch data.")
                    return pd.DataFrame() # Return kosong jika sesi tidak siap
                
                # Konversi timeframe agar sesuai dengan yang diharapkan oleh Bybit fetcher (misalnya "1h" -> "60")
                bybit_interval = timeframe
                if timeframe.endswith('h'):
                    bybit_interval = str(int(timeframe.replace('h', '')) * 60)
                elif timeframe.endswith('m'):
                    bybit_interval = timeframe.replace('m', '')
                elif timeframe == '1d':
                    bybit_interval = 'D'
                elif timeframe == '1w':
                    bybit_interval = 'W'
                elif timeframe == '1M':
                    bybit_interval = 'M'
                else:
                    logger.error(f"Unsupported timeframe format for Bybit: {timeframe}")
                    return pd.DataFrame()

                # Panggil fungsi fetch_bybit_candles secara langsung
                df = fetch_bybit_candles(
                    symbol=symbol,
                    interval=bybit_interval, # Gunakan interval yang sudah dikonversi
                    limit=candle_limit
                )
            else:
                logger.error(f"Bursa '{exchange}' tidak didukung. Harap pilih 'binance' atau 'bybit'.")
                return pd.DataFrame()

            if df.empty:
                logger.warning(f"Tidak ada data OHLCV yang diambil untuk {symbol} dari {exchange.upper()}. Tidak dapat melanjutkan analisis.")
                return # Keluar jika DataFrame kosong

            # Pastikan index adalah datetime objects dan kolom numerik
            df.index = pd.to_datetime(df.index)
            # Pastikan kolom numerik, jika belum
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce') # coerce akan mengubah non-numerik jadi NaN

            current_price = df['close'].iloc[-1]
            current_open_price = df['open'].iloc[-1]
            logger.info(f"Data OHLCV berhasil diambil. Harga Penutupan Terakhir: {current_price:.2f}, "
                        f"Harga Pembukaan Terakhir: {current_open_price:.2f}")

            # --- Hitung Indikator Klasik ---
            logger.info("\n--- Menghitung Indikator Klasik ---")
            indikator = calculate_indicators(df.copy())
            if not indikator: # Tambahkan pemeriksaan ini jika fungsi dapat mengembalikan kosong
                logger.warning("Tidak ada indikator yang dihitung. Memastikan fungsi calculate_indicators berfungsi.")
            else:
                for key, value in indikator.items():
                    if isinstance(value, (int, float)):
                        logger.info(f"  {key}: {value:.2f}")
                    else:
                        logger.info(f"  {key}: {value}")


            # --- Analisis Struktur SMC ---
            logger.info("\n--- Menganalisis Struktur SMC ---")
            smc_result = analyze_smc_structure(df.copy())
            if not smc_result: # Tambahkan pemeriksaan ini jika fungsi dapat mengembalikan kosong
                logger.warning("Tidak ada hasil analisis SMC. Memastikan fungsi analyze_smc_structure berfungsi.")
            else:
                for key, value in smc_result.items():
                    logger.info(f"  {key}: {value}")

            # --- Konfluensi ---
            logger.info("\n--- Mengevaluasi Konfluensi ---")
            signal_strength, reason = evaluate_confluence(indikator, smc_result, current_price, current_open_price)
            logger.info(f"Kekuatan Sinyal Konfluensi: {signal_strength} - Alasan: {reason}")

            # --- Bangun Sinyal Trading Akhir ---
            logger.info("\n--- Membangun Rencana Sinyal Trading ---")
            plan = generate_trading_signal(
                symbol=symbol,
                timeframe=timeframe,
                classic_indicators=indikator,
                smc_signals=smc_result,
                df=df, # Teruskan seluruh DataFrame jika diperlukan oleh signal_builder
                current_price=current_price,
                current_open_price=current_open_price
            )

            # --- Kirim ke Telegram jika sinyal valid ---
            if plan and plan.get("signal") in ["BUY", "SELL"]:
                logger.info("\n--- Sinyal Trading Dihasilkan dan Siap Dikirim ---")
                for key, value in plan.items():
                    logger.info(f"  {key}: {value}")
                
                gpt_summary = ""
                try:
                    # >>>>>> PERBAIKAN PENTING: Panggil fungsi async get_gpt_analysis dengan 'await' <<<<<<
                    # Juga, pastikan Anda meneruskan argumen yang diharapkan oleh get_gpt_analysis (plan dan smc_signals)
                    gpt_summary = await get_gpt_analysis(
                        signal_plan=plan,
                        smc_signals=smc_result # Pastikan ini diteruskan
                    )
                    logger.info("Ringkasan GPT berhasil dibuat.")
                except Exception as gpt_e:
                    logger.warning(f"Gagal mendapatkan ringkasan GPT: {gpt_e}")
                    gpt_summary = "Ringkasan AI tidak tersedia."

                # Kirim sinyal ke Telegram termasuk ringkasan GPT
                send_signal_to_telegram(plan, gpt_summary) # Modifikasi send_signal_to_telegram untuk menerima gpt_summary
                logger.info(f"Sinyal untuk {symbol} berhasil dikirim ke Telegram (termasuk ringkasan AI).")
            else:
                logger.info("⚠️ Tidak ada sinyal BUY atau SELL yang valid untuk dikirim.")

        except ImportError as e:
            logger.critical(f"❌ Error: Salah satu modul impor tidak ditemukan. Pastikan semua file ada di lokasi yang benar: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ Terjadi kesalahan tak terduga saat menganalisis {symbol}: {e}", exc_info=True)
        finally:
            logger.info(f"--- Analisis untuk {symbol} Selesai ---\n")

# --- Contoh Penggunaan (untuk pengujian) ---
if __name__ == "__main__":
    logger.info("Memulai pengujian AnalyzerEntry...")
    analyzer = AnalyzerEntry()

    # Fungsi untuk menjalankan fungsi asinkron dari luar async context
    async def run_analysis_test():
        # UNCOMMENT SALAH SATU DI BAWAH INI UNTUK MENGUJI
        await analyzer.analyze_coin(symbol="BTCUSDT", timeframe="1h", candle_limit=300, exchange="binance")
        # await analyzer.analyze_coin(symbol="SOLUSDT", timeframe="15m", candle_limit=200, exchange="bybit")
        # await analyzer.analyze_coin(symbol="NONEXISTENTPAIR", timeframe="1h", candle_limit=50, exchange="binance")
        # await analyzer.analyze_coin(symbol="FAKEBYBIT", timeframe="15m", candle_limit=50, exchange="bybit")

    # Jalankan fungsi pengujian asinkron
    asyncio.run(run_analysis_test())

    logger.info("Pengujian AnalyzerEntry selesai.")
