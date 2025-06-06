# outputs/gpt_summarizer.py

import os
# Pastikan Anda sudah menginstal 'openai' dan 'python-dotenv'
import openai
from dotenv import load_dotenv

# Asumsi: Anda memiliki utilitas logger di utils/logger.py
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.warning("utils/logger.py not found. Using basic logging for gpt_summarizer.")

# Muat variabel lingkungan di sini juga, sebagai fallback atau jika modul ini diuji terpisah
load_dotenv()

async def get_gpt_analysis(signal_plan: dict, smc_signals: dict) -> str:
    """
    Minta GPT-4o untuk membuat ringkasan naratif dari sinyal trading,
    berdasarkan data sinyal dan analisis struktur pasar SMC.

    Args:
        signal_plan (dict): Kamus yang berisi detail sinyal trading (dari signal_builder).
        smc_signals (dict): Hasil analisis struktur pasar SMC (dari smc_structure).

    Returns:
        str: Ringkasan teks yang dihasilkan oleh GPT.
             Mengembalikan pesan error jika ada masalah dengan API atau data.
    """
    # Dapatkan API Key dari environment variable
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        logger.error("OPENAI_API_KEY tidak ditemukan di environment variables. Gagal menghasilkan ringkasan GPT.")
        return "Ringkasan AI tidak tersedia: Kunci API OpenAI tidak diatur."

    # Pastikan API key diatur untuk library OpenAI
    openai.api_key = openai_api_key

    # Pastikan data yang diperlukan ada di kamus sinyal
    symbol = signal_plan.get('symbol', 'N/A')
    timeframe = signal_plan.get('timeframe', 'N/A')
    signal_type = signal_plan.get('signal', 'N/A')
    strength = signal_plan.get('strength', 'N/A')
    entry_price = signal_plan.get('entry_price', 'N/A')
    stop_loss = signal_plan.get('stop_loss', 'N/A')
    take_profit_1 = signal_plan.get('take_profit_1', 'N/A')
    take_profit_2 = signal_plan.get('take_profit_2', 'N/A')
    take_profit_3 = signal_plan.get('take_profit_3', 'N/A')
    reason = signal_plan.get('reason', 'N/A')

    # Ekstrak data SMC
    bos_choch = smc_signals.get('bos_choch', {})
    fvg = smc_signals.get('fvg', {})
    order_block = smc_signals.get('order_block', {})

    prompt = f"""
    Kamu adalah analis kripto cerdas dan ringkas. Berdasarkan data analisis teknikal berikut, buat penjelasan singkat, tajam, dan profesional sebagai narasi analisis pasar dalam **2-3 kalimat**:

    **Detail Sinyal Trading:**
    Sinyal: {signal_type} - Kekuatan: {strength}
    Simbol: {symbol} - Timeframe: {timeframe}
    Harga Entri: {entry_price}, Stop Loss: {stop_loss}
    Target Profit 1: {take_profit_1}, Target Profit 2: {take_profit_2}, Target Profit 3: {take_profit_3}
    Alasan: {reason}

    **Struktur Pasar SMC:**
    Break of Structure/Change of Character (BOS/CHOCH): {bos_choch}
    Fair Value Gap (FVG): {fvg}
    Order Block: {order_block}

    Fokuslah pada gambaran besar pasar dan potensi pergerakan harga. Hindari jargon teknikal berlebihan.
    """

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o", # Model ini mendukung input yang lebih panjang dan lebih canggih
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"Ringkasan GPT berhasil dihasilkan untuk {symbol} - {timeframe}.")
        return summary
    except openai.error.AuthenticationError:
        logger.error("Autentikasi OpenAI gagal. Periksa OPENAI_API_KEY Anda.")
        return "Ringkasan AI tidak tersedia: Autentikasi API gagal."
    except openai.error.RateLimitError:
        logger.warning("Batas rate OpenAI API tercapai. Mencoba lagi nanti.")
        return "Ringkasan AI tidak tersedia: Batas rate API tercapai."
    except Exception as e:
        logger.error(f"Terjadi kesalahan saat memanggil OpenAI API: {e}", exc_info=True)
        return f"Ringkasan AI tidak tersedia: Error tak terduga ({e})."

# --- Contoh Penggunaan (untuk pengujian) ---
if __name__ == "__main__":
    import asyncio # Diperlukan untuk menjalankan fungsi async
    
    # Dummy data untuk pengujian
    dummy_signal_plan = {
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'signal': 'BUY',
        'strength': 'strong_bullish',
        'entry_price': 60000.0,
        'stop_loss': 59000.0,
        'take_profit_1': 61000.0,
        'take_profit_2': 62000.0,
        'take_profit_3': 63000.0,
        'reason': 'Harga memantul dari zona demand kuat dengan volume tinggi.'
    }
    dummy_smc_signals = {
        'bos_choch': {'type': 'CHOCH', 'direction': 'bullish', 'level': 59500.0},
        'fvg': {'type': 'bullish_fvg', 'zone': [59700.0, 59800.0]},
        'order_block': {'bullish_ob': [59600.0, 59700.0], 'bearish_ob': None}
    }

    async def test_gpt_analysis():
        logger.info("Memulai pengujian get_gpt_analysis...")
        summary = await get_gpt_analysis(dummy_signal_plan, dummy_smc_signals)
        logger.info(f"\n--- Ringkasan GPT yang Dihasilkan ---\n{summary}")
        logger.info("Pengujian get_gpt_analysis selesai.")

    # Jalankan fungsi async
    asyncio.run(test_gpt_analysis())
