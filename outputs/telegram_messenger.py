# File: outputs/telegram_messenger.py
# Tujuan: Mengirim sinyal trading dan ringkasan analisis ke Telegram.

import logging
import requests
import os
import json # Import json module

logger = logging.getLogger(__name__)

# --- KONFIGURASI TELEGRAM (Harus dimuat dari config_loader di aplikasi utama) ---
# Untuk pengujian mandiri atau jika belum terintegrasi dengan ConfigLoader
# Anda perlu mengisi ini secara manual atau dari lingkungan.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")

if "YOUR_TELEGRAM_BOT_TOKEN_HERE" in TELEGRAM_BOT_TOKEN or "YOUR_TELEGRAM_CHAT_ID_HERE" in TELEGRAM_CHAT_ID:
    logger.warning("Telegram Bot Token atau Chat ID belum dikonfigurasi. Pengiriman sinyal akan gagal.")
    logger.warning("Harap atur variabel lingkungan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID.")

def send_signal_to_telegram(message: str):
    """
    Mengirim pesan teks ke grup atau channel Telegram.

    Args:
        message (str): Pesan teks yang akan dikirim (sudah diformat).
    """
    if "YOUR_TELEGRAM_BOT_TOKEN_HERE" in TELEGRAM_BOT_TOKEN or "YOUR_TELEGRAM_CHAT_ID_HERE" in TELEGRAM_CHAT_ID:
        logger.error("Gagal mengirim sinyal Telegram: Token atau Chat ID tidak dikonfigurasi.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML" # Atau "MarkdownV2" jika Anda menggunakan format Markdown yang lebih kompleks
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # Akan memunculkan HTTPError untuk status kode 4xx/5xx
        logger.info("Sinyal berhasil dikirim ke Telegram.")
        logger.debug(f"Telegram API response: {response.json()}")
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while sending Telegram message: {http_err} - Response: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred while sending Telegram message: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred while sending Telegram message: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"An unexpected error occurred while sending Telegram message: {req_err}")
    except Exception as e:
        logger.error(f"An unknown error occurred while sending Telegram message: {e}", exc_info=True)


def format_signal_table(signal_plan: dict, confluence_reason: str) -> str:
    """
    Memformat detail sinyal trading ke dalam bentuk tabel yang mudah dibaca untuk Telegram.

    Args:
        signal_plan (dict): Kamus yang berisi rencana sinyal trading.
        confluence_reason (str): String alasan konfluensi dari evaluator.

    Returns:
        str: Pesan yang diformat dalam HTML (atau Markdown) untuk Telegram.
    """
    symbol = signal_plan.get("symbol", "N/A")
    timeframe = signal_plan.get("timeframe", "N/A")
    signal = signal_plan.get("signal", "N/A")
    entry_price = signal_plan.get("entry_price", "N/A")
    stop_loss = signal_plan.get("stop_loss", "N/A")
    take_profit = signal_plan.get("take_profit", "N/A")
    risk_reward_ratio = signal_plan.get("risk_reward_ratio", "N/A")
    confluence_sentiment = signal_plan.get("confluence_sentiment", "N/A")
    current_price = signal_plan.get("current_price", "N/A")
    # reason adalah list di signal_plan, join menjadi string jika perlu
    signal_reasons_list = signal_plan.get("reason", [])
    signal_reasons = "\n".join([f"• {r}" for r in signal_reasons_list]) if signal_reasons_list else "Tidak ada alasan spesifik."


    message_parts = []
    message_parts.append(f"<b>📈 Sinyal Trading Baru: {symbol.upper()}</b>")
    message_parts.append(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    message_parts.append(f"Bursa: {signal_plan.get('exchange', 'N/A').upper()} | Timeframe: {timeframe.upper()}")
    message_parts.append(f"------------------------------------")
    message_parts.append(f"Sinyal: <b>{signal}</b> (Konfluensi: {confluence_sentiment})")
    message_parts.append(f"Harga Saat Ini: <code>{current_price}</code>")
    message_parts.append(f"Harga Masuk (Target): <code>{entry_price}</code>")
    message_parts.append(f"Stop Loss (SL): <code>{stop_loss}</code>")
    message_parts.append(f"Take Profit (TP): <code>{take_profit}</code>")
    message_parts.append(f"Rasio R/R: <b>{risk_reward_ratio}</b>")
    message_parts.append(f"------------------------------------")
    message_parts.append(f"<b>Alasan Konfluensi:</b>")
    message_parts.append(confluence_reason) # Ini sudah string gabungan dari analyzer_entry
    message_parts.append("\n<b>Detail Sinyal:</b>")
    message_parts.append(signal_reasons)
    message_parts.append(f"------------------------------------")
    message_parts.append(f"<i>Disclaimer: Analisis ini bersifat otomatis dan bukan nasihat keuangan.</i>")

    return "\n".join(message_parts)

# Untuk pengujian mandiri
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("--- Menguji Pengiriman Sinyal Telegram ---")

    # Data dummy untuk signal_plan (sesuai format generate_trading_signal)
    dummy_signal_plan = {
        "signal": "BUY",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "entry_price": "60000.50",
        "stop_loss": "59500.00",
        "take_profit": "61000.00",
        "risk_reward_ratio": "2.00",
        "reason": ["EMA: Bullish Trend", "SMC: Bullish CHoCH Detected", "Orderbook: Strong Bid Wall"],
        "confluence_sentiment": "BULLISH",
        "current_price": "60000.25",
        "exchange": "Binance"
    }
    
    dummy_confluence_reason = "EMA Bullish Trend, SMC Bullish CHoCH Detected, Orderbook Strong Bid Wall."

    # Format pesan tabel
    formatted_table = format_signal_table(dummy_signal_plan, dummy_confluence_reason)
    print("\n--- Pesan yang Diformat ---")
    print(formatted_table)

    # # Untuk benar-benar mengirim ke Telegram, Anda perlu mengatur TOKEN dan CHAT_ID
    # # dan uncomment baris di bawah ini:
    # print("\n--- Mencoba mengirim ke Telegram (pastikan TOKEN & CHAT_ID diatur) ---")
    # send_signal_to_telegram(formatted_table) # Kirim pesan tabel yang diformat
    # print("Pengujian pengiriman sinyal selesai.")
