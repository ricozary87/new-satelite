# File: analyzer_entry.py
# Tujuan: Titik masuk utama untuk mengumpulkan data pasar dari berbagai bursa
# dan mengintegrasikannya dengan analisis serta logika sinyal.

import sys
import os
import logging
import numpy as np
import pandas as pd
import asyncio
from datetime import datetime, timedelta

# Tambahkan direktori root proyek ke sys.path
# Ini memastikan modul-modul kustom seperti 'utils' dan 'data_sources' dapat diimpor.
current_dir = os.path.dirname(os.path.abspath(__file__))
# Asumsi struktur: project_root/data_sources, project_root/utils, project_root/analyzers, etc.
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Impor modul logging kustom
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    # Fallback ke logging dasar jika modul kustom tidak ditemukan
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging.")

# Impor modul konfigurasi
try:
    from utils.config_loader import ConfigLoader
except ImportError:
    logger.critical("Error: utils/config_loader.py not found. Please ensure it exists.")
    ConfigLoader = None # Set to None if import fails to prevent further errors

# Impor data fetcher yang sudah disempurnakan
# market_data_fetcher sekarang seharusnya menangani semua jenis data dari Binance & Bybit
import data_sources.market_data_fetcher as market

# Impor modul-modul analisis dan logika (asumsi path sudah benar melalui sys.path)
from analyzers.classic_indicators import calculate_indicators
from analyzers.smc_structure import analyze_smc_structure
# Pastikan ini mengimpor fungsi evaluate_market_confluence, bukan evaluate_confluence
from logic_engine.confluence_checker import evaluate_market_confluence
from logic_engine.signal_builder import generate_trading_signal
from outputs.telegram_messenger import send_signal_to_telegram, format_signal_table
from outputs.gpt_summarizer import get_gpt_analysis


class AnalyzerEntry:
    def __init__(self):
        """
        Menginisialisasi AnalyzerEntry, memuat konfigurasi.
        Memastikan ConfigLoader tersedia sebelum melanjutkan.
        """
        if ConfigLoader is None:
            logger.critical("ConfigLoader not available. Exiting AnalyzerEntry initialization.")
            self.config = None
            return

        self.config = ConfigLoader().load_config()
        # Menghapus inisialisasi fetcher lama karena sekarang semua melalui market_data_fetcher
        # self.binance_fetcher = BinanceCandleFetcher() # Dihapus
        logger.info("AnalyzerEntry initialized and config loaded.")

    async def analyze_coin(self, symbol: str, timeframe: str = "1h", candle_limit: int = 300, exchange: str = "binance"):
        """
        Melakukan analisis pasar lengkap untuk simbol dan timeframe yang diberikan.
        Mengumpulkan data, menghitung indikator, menganalisis struktur, mengevaluasi konfluensi,
        membangun sinyal trading, dan mengirimkan notifikasi.

        Args:
            symbol (str): Simbol pasangan perdagangan (misalnya, "BTCUSDT").
            timeframe (str): Timeframe candlestick (misalnya, "1h", "4h", "1d").
            candle_limit (int): Jumlah candlestick yang akan diambil.
            exchange (str): Bursa untuk analisis ("binance" atau "bybit").
        """
        logger.info(f"\n--- Memulai Analisis untuk {symbol} di {exchange.upper()} Timeframe {timeframe} ---")

        # Inisialisasi kamus untuk mengumpulkan semua data
        # Data ini akan menjadi input untuk evaluate_market_confluence
        collected_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange,
            "ohlcv_df": pd.DataFrame(), # DataFrame untuk data candlestick
            "classic_indicators": {},
            "smc_signals": {},
            "current_price": None,
            "current_open_price": None,
            "market_data_additional": { # Data tambahan dari market_data_fetcher
                "binance_spot": {},
                "binance_futures": {},
                "bybit": {}
            },
            "confluence_result": {} # Tambahkan ini untuk menyimpan hasil konfluensi
        }

        # --- Bagian 1: Pengambilan Data Candlestick (OHLCV) ---
        df_candles = pd.DataFrame()
        try:
            logger.info(f"Mengambil {candle_limit} candle data dari {exchange.upper()}...")
            if exchange.lower() == "binance":
                df_candles_raw = market.fetch_binance_spot_klines(
                    symbol=symbol,
                    interval=timeframe,
                    limit=candle_limit
                )
                if df_candles_raw:
                    # Konversi data mentah Binance klines ke DataFrame
                    df_candles = pd.DataFrame(df_candles_raw, columns=[
                        'open_time', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_asset_volume', 'number_of_trades',
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                    ])
                    df_candles['open_time'] = pd.to_datetime(df_candles['open_time'], unit='ms')
                    df_candles.set_index('open_time', inplace=True)
                    # Hanya simpan kolom OHLCV yang relevan dan konversi ke numerik
                    df_candles = df_candles[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
                    logger.info(f"Binance Spot Candlestick data berhasil diambil. Jumlah baris: {len(df_candles)}")
                else:
                    logger.warning(f"Binance Spot Candlestick data kosong atau gagal diambil untuk {symbol}.")

            elif exchange.lower() == "bybit":
                # Konversi timeframe ke format Bybit
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
                    logger.error(f"Format timeframe tidak didukung untuk Bybit: {timeframe}")
                    return None # Mengembalikan None jika format timeframe tidak valid

                df_candles_raw_bybit = market.fetch_bybit_kline(
                    symbol=symbol,
                    interval=bybit_interval,
                    limit=candle_limit
                )
                if df_candles_raw_bybit and df_candles_raw_bybit.get('result') and df_candles_raw_bybit['result'].get('list'):
                    # Bybit returns data in reverse chronological order (newest first)
                    # Need to reverse it to oldest first for proper indicator calculation
                    df_candles_list = df_candles_raw_bybit['result']['list'][::-1] # Reverse the list
                    df_candles = pd.DataFrame(df_candles_list, columns=[
                        'start', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                    ])
                    df_candles['start'] = pd.to_datetime(df_candles['start'], unit='ms')
                    df_candles.set_index('start', inplace=True)
                    # Hanya simpan kolom OHLCV yang relevan dan konversi ke numerik
                    df_candles = df_candles[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
                    logger.info(f"Bybit Candlestick data berhasil diambil. Jumlah baris: {len(df_candles)}")
                else:
                    logger.warning(f"Bybit Candlestick data kosong atau gagal diambil untuk {symbol}.")

            else:
                logger.error(f"Bursa '{exchange}' tidak didukung. Harap pilih 'binance' atau 'bybit'.")
                return None # Mengembalikan None jika bursa tidak didukung

            if df_candles.empty:
                logger.warning(f"Tidak ada data OHLCV yang valid yang tersedia untuk {symbol} dari {exchange.upper()}. Menghentikan analisis.")
                return None # Menghentikan analisis jika tidak ada data candlestick

            collected_data["ohlcv_df"] = df_candles.copy() # Simpan DataFrame ke collected_data
            # Pastikan DataFrame tidak kosong sebelum mengakses iloc
            if not df_candles.empty:
                collected_data["current_price"] = df_candles['close'].iloc[-1]
                collected_data["current_open_price"] = df_candles['open'].iloc[-1]
            else:
                collected_data["current_price"] = None
                collected_data["current_open_price"] = None

            logger.info(f"Data OHLCV berhasil diambil. Harga Penutupan Terakhir: {collected_data['current_price']:.2f if collected_data['current_price'] is not None else 'N/A'}, Harga Pembukaan Terakhir: {collected_data['current_open_price']:.2f if collected_data['current_open_price'] is not None else 'N/A'}")

        except Exception as e:
            logger.error(f"Gagal mengambil atau memproses data candlestick untuk {symbol} dari {exchange.upper()}: {e}", exc_info=True)
            return None # Mengembalikan None jika terjadi kesalahan fatal pada tahap ini

        # --- Bagian 2: Menghitung Indikator Klasik ---
        logger.info("\n--- Menghitung Indikator Klasik ---")
        indikator = calculate_indicators(collected_data["ohlcv_df"].copy())
        collected_data["classic_indicators"] = indikator # Simpan indikator ke collected_data
        if indikator:
            for key, value in indikator.items():
                if isinstance(value, (int, float)):
                    logger.info(f"  {key}: {value:.2f}")
                else:
                    logger.info(f"  {key}: {value}")
        else:
            logger.warning("Tidak ada indikator yang dihitung.")

        # --- Bagian 3: Menganalisis Struktur SMC ---
        logger.info("\n--- Menganalisis Struktur SMC ---")
        smc_result = analyze_smc_structure(collected_data["ohlcv_df"].copy())
        collected_data["smc_signals"] = smc_result # Simpan hasil SMC ke collected_data
        if smc_result:
            for key, value in smc_result.items():
                logger.info(f"  {key}: {value}")
        else:
            logger.warning("Tidak ada hasil analisis SMC.")

        # --- Bagian 4: Mengambil Data Market Tambahan ---
        logger.info("\n--- Mengambil Data Market Tambahan ---")
        # Penting: Sesuaikan simbol untuk futures jika berbeda dengan spot, BTCUSDT biasanya sama
        futures_symbol = symbol # Asumsi simbol futures sama dengan spot (BTCUSDT)

        # Data Binance Spot
        collected_data["market_data_additional"]["binance_spot"]["orderbook"] = market.fetch_binance_spot_orderbook(symbol, limit=100)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_spot"]["aggtrades"] = market.fetch_binance_spot_aggtrades(symbol, limit=50)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_spot"]["24h_stats"] = market.fetch_binance_spot_24h_stats(symbol)
        await asyncio.sleep(0.1)
        # collected_data["market_data_additional"]["binance_spot"]["exchange_info"] = market.fetch_binance_spot_exchange_info() # Umumnya tidak perlu di setiap analisis

        # Data Binance Futures
        collected_data["market_data_additional"]["binance_futures"]["funding_rate"] = market.fetch_binance_futures_funding_rate(futures_symbol)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_futures"]["open_interest"] = market.fetch_binance_futures_open_interest(futures_symbol)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_futures"]["long_short_account_ratio"] = market.fetch_binance_futures_long_short_account_ratio(futures_symbol, period='5m') # Period '5m' atau '1h'
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_futures"]["long_short_position_ratio"] = market.fetch_binance_futures_long_short_position_ratio(futures_symbol, period='5m') # Period '5m' atau '1h'
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["binance_futures"]["taker_buy_sell_volume"] = market.fetch_binance_futures_taker_buy_sell_volume(futures_symbol, period='5m') # Period '5m' atau '1h'
        await asyncio.sleep(0.1)
        # collected_data["market_data_additional"]["binance_futures"]["exchange_info"] = market.fetch_binance_futures_exchange_info() # Umumnya tidak perlu di setiap analisis

        # Data Bybit
        collected_data["market_data_additional"]["bybit"]["orderbook"] = market.fetch_bybit_orderbook(symbol, limit=50)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["bybit"]["funding_rate"] = market.fetch_bybit_funding_rate(symbol)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["bybit"]["open_interest"] = market.fetch_bybit_open_interest(symbol, interval_time=60)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["bybit"]["tickers"] = market.fetch_bybit_tickers(symbol)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["bybit"]["recent_trade_list"] = market.fetch_bybit_recent_trade_list(symbol, limit=50)
        await asyncio.sleep(0.1)
        collected_data["market_data_additional"]["bybit"]["long_short_ratio"] = market.fetch_bybit_long_short_ratio(symbol, period='5min') # Period '5min' atau '1h'
        await asyncio.sleep(0.1)
        # collected_data["market_data_additional"]["bybit"]["exchange_info"] = market.fetch_bybit_exchange_info(category="linear") # Umumnya tidak perlu di setiap analisis

        # --- Bagian 5: Mengevaluasi Konfluensi ---
        logger.info("\n--- Mengevaluasi Konfluensi ---")
        # Sekarang kita meneruskan seluruh kamus collected_data ke evaluate_market_confluence
        confluence_result = evaluate_market_confluence(market_data=collected_data)

        # Simpan hasil konfluensi ke collected_data
        collected_data["confluence_result"] = confluence_result
        
        # Ekstrak signal_strength dan reason dari hasil konfluensi
        signal_strength = confluence_result.get("overall_sentiment", "NETRAL")
        # Membangun string alasan dari sinyal-sinyal individu yang tidak 'N/A'
        reason = ", ".join([f"{k}: {v}" for k, v in confluence_result.get("signals", {}).items() if v != "N/A"])
        if not reason: # Jika tidak ada alasan spesifik
            reason = "Tidak ada sinyal konfluensi spesifik yang kuat."

        logger.info(f"Kekuatan Sinyal Konfluensi: {signal_strength} - Alasan: {reason}")


        # --- Bagian 6: Membangun Rencana Sinyal Trading ---
        logger.info("\n--- Membangun Rencana Sinyal Trading ---")
        # Pastikan generate_trading_signal menerima semua data yang diperlukan
        plan = generate_trading_signal(
            symbol=symbol,
            timeframe=timeframe,
            classic_indicators=collected_data["classic_indicators"],
            smc_signals=collected_data["smc_signals"],
            df=collected_data["ohlcv_df"], # Menggunakan DataFrame yang sudah ada
            current_price=collected_data["current_price"],
            current_open_price=collected_data["current_open_price"],
            confluence_result=confluence_result # Tambahkan hasil konfluensi sebagai input
        )

        # --- Bagian 7: Mengirim Sinyal ---
        if plan and plan.get("signal") in ["BUY", "SELL"]:
            logger.info("\n--- Sinyal Trading Dihasilkan dan Siap Dikirim ---")
            for key, value in plan.items():
                logger.info(f"  {key}: {value}")

            gpt_summary = ""
            try:
                # Pastikan gpt_summarizer bisa memproses format plan dan smc_signals
                # Menambahkan market_insight yang berisi 'reason' untuk konteks GPT
                gpt_summary = await get_gpt_analysis(
                    signal_plan=plan,
                    smc_signals=collected_data["smc_signals"],
                    market_insight=reason # Meneruskan alasan konfluensi ke GPT
                )
                logger.info("Ringkasan GPT berhasil dibuat.")
            except Exception as gpt_e:
                logger.warning(f"Gagal mendapatkan ringkasan GPT: {gpt_e}")
                gpt_summary = "Ringkasan AI tidak tersedia."

            # Memformat sinyal ke tabel sebelum mengirim
            table_summary = format_signal_table(plan, reason)
            
            # Mengirimkan sinyal ke Telegram (menggabungkan ringkasan GPT dan tabel)
            # send_signal_to_telegram harus menerima string pesan lengkap
            full_telegram_message = f"{gpt_summary}\n\n{table_summary}"
            send_signal_to_telegram(full_telegram_message) # Mengirim pesan gabungan
            logger.info(f"Sinyal untuk {symbol} berhasil dikirim ke Telegram.")
        else:
            logger.info("⚠️ Tidak ada sinyal BUY atau SELL yang valid untuk dikirim.")

        # --- Penanganan Kesalahan Akhir dan Pengembalian Data ---
        return collected_data # Mengembalikan semua data yang terkumpul dan hasil analisis

    except ImportError as e:
        logger.critical(f"❌ Error: Salah satu modul impor tidak ditemukan: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Terjadi kesalahan tak terduga saat menganalisis {symbol}: {e}", exc_info=True)
        return None
    finally:
        logger.info(f"--- Analisis untuk {symbol} Selesai ---\n")

# Inisialisasi instance AnalyzerEntry di tingkat modul
# Ini agar tidak perlu membuat instance AnalyzerEntry berulang kali
_analyzer_instance = AnalyzerEntry()

# Fungsi async yang diekspos untuk memanggil analisis
async def analyze_coin(symbol: str, timeframe: str = "1h", candle_limit: int = 300, exchange: str = "binance"):
    """
    Fungsi pembungkus untuk memanggil metode analisis dari AnalyzerEntry.
    """
    # Pastikan konfigurasi sudah dimuat dengan benar saat inisialisasi _analyzer_instance
    if _analyzer_instance.config is None:
        logger.critical("AnalyzerEntry tidak diinisialisasi dengan benar karena ConfigLoader tidak tersedia. Aborting analysis.")
        return None
    return await _analyzer_instance.analyze_coin(symbol, timeframe, candle_limit, exchange)

if __name__ == "__main__":
    logger.info("Memulai pengujian AnalyzerEntry...")
    # Pastikan inisialisasi AnalyzerEntry dilakukan sekali di awal
    # _analyzer_instance sudah dibuat di atas, jadi tidak perlu membuat baru di sini.

    async def run_analysis_test():
        # Contoh analisis untuk Binance Spot
        logger.info("\n--- Menjalankan Analisis BTCUSDT di Binance (Spot) ---")
        result_binance = await analyze_coin(symbol="BTCUSDT", timeframe="1h", candle_limit=100, exchange="binance")
        if result_binance:
            # Contoh mencetak beberapa hasil utama
            print("\n--- Hasil Analisis Binance BTCUSDT (1h) ---")
            print(f"Harga Terakhir: {result_binance.get('current_price', 'N/A'):.2f}")
            print(f"Sentimen Keseluruhan: {result_binance.get('confluence_result', {}).get('overall_sentiment', 'N/A')}")
            print(f"Classic Indicators (RSI): {result_binance.get('classic_indicators', {}).get('RSI', 'N/A'):.2f}")
            print(f"SMC Signals (Market Structure): {result_binance.get('smc_signals', {}).get('market_structure', 'N/A')}")
        else:
            print("\nAnalisis Binance gagal.")

        # Memberi jeda sebelum analisis Bybit untuk menghindari batasan rate
        await asyncio.sleep(5)

        # Contoh analisis untuk Bybit
        logger.info("\n--- Menjalankan Analisis ETHUSDT di Bybit (Linear Futures) ---")
        result_bybit = await analyze_coin(symbol="ETHUSDT", timeframe="1h", candle_limit=100, exchange="bybit")
        if result_bybit:
            print("\n--- Hasil Analisis Bybit ETHUSDT (1h) ---")
            print(f"Harga Terakhir: {result_bybit.get('current_price', 'N/A'):.2f}")
            print(f"Sentimen Keseluruhan: {result_bybit.get('confluence_result', {}).get('overall_sentiment', 'N/A')}")
            # Akses nested dictionary dengan aman
            bybit_tickers_data = result_bybit['market_data_additional']['bybit'].get('tickers')
            if bybit_tickers_data and bybit_tickers_data.get('result') and bybit_tickers_data['result'].get('list'):
                print(f"Bybit Tickers Last Price: {bybit_tickers_data['result']['list'][0].get('lastPrice')}")
            else:
                print("Bybit Tickers Last Price: N/A")
        else:
            print("\nAnalisis Bybit gagal.")


    # Menjalankan fungsi pengujian asinkron
    asyncio.run(run_analysis_test())
    logger.info("Pengujian AnalyzerEntry selesai.")
