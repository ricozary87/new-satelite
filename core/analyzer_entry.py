import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Impor modul-modul yang diperlukan
# Pastikan semua file ini ada di lokasi yang benar
from analyzers.classic_indicators import calculate_indicators
from analyzers.smc_structure import analyze_smc_structure
from logic_engine.confluence_checker import evaluate_confluence
from logic_engine.signal_builder import generate_trading_signal # <-- PERBAIKAN DI SINI
from outputs.telegram_messenger import send_signal_to_telegram

# Konfigurasi logging agar lebih informatif
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def analyze_coin(symbol: str, timeframe: str = "1h", candle_limit: int = 300):
    """
    Menganalisis data OHLCV untuk pasangan koin tertentu, menghitung indikator,
    menganalisis struktur pasar, mengevaluasi konfluensi, membangun sinyal,
    dan mengirimkannya ke Telegram jika valid.

    Args:
        symbol (str): Simbol pasangan koin (misalnya, "SOLUSDT").
        timeframe (str): Timeframe candle (misalnya, "1h", "4h").
        candle_limit (int): Jumlah candle data yang akan diambil/disimulasikan.
    """
    logging.info(f"\n--- Memulai Analisis untuk {symbol} di Timeframe {timeframe} ---")

    try:
        # --- Simulasi Pengambilan Data OHLCV ---
        # Catatan: Dalam produksi, bagian ini akan diganti dengan panggilan API bursa.
        logging.info(f"Mengambil {candle_limit} candle data simulasi...")
        
        now = datetime.now()
        # Sesuaikan interval untuk simulasi agar lebih sesuai dengan timeframe "1h"
        # Misalnya, jika 1h, maka timedelta harus dalam jam, bukan menit
        if timeframe == "1h":
            interval = timedelta(hours=1)
        elif timeframe == "4h":
            interval = timedelta(hours=4)
        else: # Default ke 1 jam jika timeframe tidak dikenal
            interval = timedelta(hours=1) 
        
        timestamps = [now - (interval * i) for i in range(candle_limit)][::-1]
        
        # Contoh data simulasi yang sedikit lebih realistis
        # Harga bisa memiliki tren atau volatilitas acak
        base_price = 200
        np.random.seed(42) # Untuk hasil yang bisa direproduksi
        
        open_prices = base_price + np.cumsum(np.random.normal(0, 1, candle_limit))
        close_prices = open_prices + np.random.normal(0, 2, candle_limit)
        high_prices = np.maximum(open_prices, close_prices) + np.abs(np.random.normal(0, 3, candle_limit))
        low_prices = np.minimum(open_prices, close_prices) - np.abs(np.random.normal(0, 3, candle_limit))

        # Pastikan low tidak lebih tinggi dari open/close/high dan high tidak lebih rendah dari open/close/low
        high_prices = np.maximum(high_prices, np.maximum(open_prices, close_prices))
        low_prices = np.minimum(low_prices, np.minimum(open_prices, close_prices))

        # Volume acak
        volume_prices = np.random.uniform(500, 2000, candle_limit)

        data = {
            "timestamp": timestamps,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume_prices
        }
        df = pd.DataFrame(data)

        # Pastikan kolom timestamp diatur sebagai index
        df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index) # Pastikan index adalah datetime objects

        logging.info("Data simulasi OHLCV berhasil dibuat.")
        if not df.empty:
            logging.info(f"Harga Penutupan Terakhir: {df['close'].iloc[-1]:.2f}, "
                         f"Harga Pembukaan Terakhir: {df['open'].iloc[-1]:.2f}")
            current_price = df['close'].iloc[-1] # Dapatkan harga penutupan terakhir
            current_open_price = df['open'].iloc[-1] # Dapatkan harga pembukaan terakhir
        else:
            logging.warning("DataFrame simulasi kosong. Tidak dapat melanjutkan analisis.")
            return # Keluar jika DataFrame kosong

        # --- Hitung Indikator Klasik ---
        logging.info("\n--- Menghitung Indikator Klasik ---")
        indikator = calculate_indicators(df.copy()) # Teruskan salinan untuk menghindari modifikasi asli
        if not indikator:
            logging.warning("Tidak ada indikator yang dihitung. Memastikan fungsi calculate_indicators berfungsi.")
        else:
            for key, value in indikator.items():
                logging.info(f"  {key}: {value}")

        # --- Analisis Struktur SMC ---
        logging.info("\n--- Menganalisis Struktur SMC ---")
        smc_result = analyze_smc_structure(df.copy()) # Teruskan salinan untuk menghindari modifikasi asli
        if not smc_result:
            logging.warning("Tidak ada hasil analisis SMC. Memastikan fungsi analyze_smc_structure berfungsi.")
        else:
            for key, value in smc_result.items():
                logging.info(f"  {key}: {value}")

        # --- Konfluensi ---
        logging.info("\n--- Mengevaluasi Konfluensi ---")
        # evaluate_confluence membutuhkan current_price dan current_open_price
        signal_strength, reason = evaluate_confluence(indikator, smc_result, current_price, current_open_price) # <-- PERBAIKAN DI SINI
        logging.info(f"Kekuatan Sinyal Konfluensi: {signal_strength} - Alasan: {reason}")

        # --- Bangun Sinyal Trading Akhir ---
        logging.info("\n--- Membangun Rencana Sinyal Trading ---")
        # generate_trading_signal membutuhkan semua argumen ini:
        plan = generate_trading_signal( # <-- PERBAIKAN DI SINI
            symbol=symbol,
            timeframe=timeframe,
            classic_indicators=indikator,
            smc_signals=smc_result,
            df=df, # <-- TAMBAH ARGUMEN INI
            current_price=current_price, # <-- TAMBAH ARGUMEN INI
            current_open_price=current_open_price # <-- TAMBAH ARGUMEN INI
        )

        # --- Kirim ke Telegram jika sinyal valid ---
        if plan and plan.get("signal") in ["BUY", "SELL"]:
            logging.info("\n--- Sinyal Trading Dihasilkan dan Siap Dikirim ---")
            for key, value in plan.items():
                logging.info(f"  {key}: {value}")
            send_signal_to_telegram(plan)
            logging.info(f"Sinyal untuk {symbol} berhasil dikirim ke Telegram.")
        else:
            logging.info("⚠️ Tidak ada sinyal BUY atau SELL yang valid untuk dikirim.")

    except ImportError as e:
        logging.critical(f"❌ Error: Salah satu modul impor tidak ditemukan. Pastikan semua file ada: {e}")
    except Exception as e:
        logging.error(f"❌ Terjadi kesalahan tak terduga saat menganalisis {symbol}: {e}", exc_info=True)
    finally:
        logging.info(f"--- Analisis untuk {symbol} Selesai ---\n")
