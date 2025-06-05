# === FILE: outputs/telegram_messenger.py ===
import requests # Pastikan Anda sudah menginstal library 'requests' (pip install requests)
import os
import logging # Tambahkan logging untuk pesan yang lebih konsisten

logger = logging.getLogger(__name__) # Mendapatkan logger untuk modul ini

class TelegramMessenger:
    """
    Kelas untuk mengirim pesan ke Telegram melalui Bot API.
    """
    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            logger.warning("Peringatan: Telegram BOT_TOKEN atau CHAT_ID tidak ditemukan. Pesan tidak akan terkirim.")
            self.bot_token = None
            self.chat_id = None
            self.base_url = None
        else:
            self.bot_token = bot_token
            self.chat_id = chat_id
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            logger.info(f"Telegram Messenger siap. Chat ID: {self.chat_id}")

    def send_message(self, message: str):
        """
        Mengirim pesan teks ke chat Telegram yang ditentukan.

        Args:
            message (str): Pesan yang akan dikirim.
        """
        if not self.bot_token or not self.chat_id:
            logger.error("❌ Telegram Messenger tidak dikonfigurasi. Pesan tidak terkirim.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML" # Mengizinkan format HTML seperti <b>, <i>
        }
        try:
            response = requests.post(self.base_url, data=payload)
            response.raise_for_status() # Akan menimbulkan HTTPError untuk status kode 4xx/5xx
            logger.info("✅ Pesan Telegram berhasil dikirim.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP Error saat mengirim pesan Telegram: {e}")
            logger.error(f"Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection Error saat mengirim pesan Telegram: {e}")
        except Exception as e:
            logger.error(f"❌ Error tidak dikenal saat mengirim pesan Telegram: {e}")


# --- FUNGSI PEMBANTU (WRAPPER) UNTUK DIIMPOR ---
# Ini adalah fungsi yang akan dipanggil dari analyzer_entry.py
def send_signal_to_telegram(signal_data: dict):
    """
    Mengirim detail sinyal trading yang diformat ke Telegram.

    Args:
        signal_data (dict): Dictionary yang berisi detail sinyal trading.
                            Contoh:
                            {
                                "symbol": "BTC/USDT",
                                "timeframe": "1h",
                                "signal": "BUY",
                                "strength": "strong_buy",
                                "entry_price": 20000.0,
                                "stop_loss": 19500.0,
                                "take_profit_1": 20500.0,
                                "take_profit_2": 21000.0,
                                "take_profit_3": 21500.0,
                                "risk_reward_ratio_base": "1:1",
                                "reason": "Bullish trend, structure break, FVG reaction"
                            }
    """
    # Pastikan variabel lingkungan dimuat
    from dotenv import load_dotenv
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    messenger = TelegramMessenger(bot_token, chat_id)

    if signal_data.get("signal") == "NO_SIGNAL":
        message_text = f"<b>[{signal_data.get('symbol')}/{signal_data.get('timeframe')}]</b>\n" \
                       f"⚠️ Tidak Ada Sinyal Trading\n" \
                       f"Alasan: {signal_data.get('reason', 'N/A')}"
        logger.info("Tidak ada sinyal valid untuk dikirim ke Telegram.")
        return # Jangan kirim jika tidak ada sinyal

    # Format pesan berdasarkan tipe sinyal
    signal_type_display = signal_data.get("signal", "N/A")
    if signal_type_display == "BUY":
        signal_type_display = "🟢 BUY Signal 🟢"
    elif signal_type_display == "SELL":
        signal_type_display = "🔴 SELL Signal 🔴"
    
    # Menentukan emoji kekuatan sinyal
    strength_emoji_map = {
        "strong_buy": "🔥🔥 STRONG BUY",
        "moderate_buy": "📈 Moderate Buy",
        "potential_buy": "💡 Potential Buy",
        "strong_sell": "📉📉 STRONG SELL",
        "moderate_sell": "📊 Moderate Sell",
        "potential_sell": "💡 Potential Sell",
        "no_signal": "⚪️ No Signal" # Seharusnya tidak tercapai karena sudah ada filter di atas
    }
    strength_display = strength_emoji_map.get(signal_data.get("strength"), signal_data.get("strength", "N/A").replace('_', ' ').title())


    message_text = (
        f"<b>[{signal_data.get('symbol')}/{signal_data.get('timeframe')}]</b>\n"
        f"{signal_type_display} - <b>{strength_display}</b>\n\n"
        f"➡️ Entry: <code>{signal_data.get('entry_price', 'N/A'):.4f}</code>\n"
        f"🛑 Stop Loss: <code>{signal_data.get('stop_loss', 'N/A'):.4f}</code>\n"
        f"🎯 TP1: <code>{signal_data.get('take_profit_1', 'N/A'):.4f}</code> (RRR: {signal_data.get('risk_reward_ratio_base', 'N/A')})\n"
        f"🎯 TP2: <code>{signal_data.get('take_profit_2', 'N/A'):.4f}</code>\n"
        f"🎯 TP3: <code>{signal_data.get('take_profit_3', 'N/A'):.4f}</code>\n\n"
        f"ℹ️ Reason: {signal_data.get('reason', 'N/A')}\n"
        f"<i>(Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')})</i>"
    )
    
    # Kirim pesan menggunakan instance TelegramMessenger
    messenger.send_message(message_text)


# Contoh penggunaan (untuk pengujian mandiri file ini)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n--- Testing Telegram Messenger Class and Wrapper Function ---")

    # Pastikan Anda memiliki variabel ini di file .env Anda
    # TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
    # TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
    # Contoh penggunaan dummy untuk pengujian wrapper function
    dummy_signal_buy = {
        "symbol": "ETH/USDT",
        "timeframe": "4h",
        "signal": "BUY",
        "strength": "strong_buy",
        "entry_price": 3500.25,
        "stop_loss": 3450.10,
        "take_profit_1": 3550.40,
        "take_profit_2": 3600.50,
        "take_profit_3": 3650.60,
        "risk_reward_ratio_base": "1:1.5",
        "reason": "EMA bullish, MACD confirms, bullish BOS, price reacts to FVG."
    }

    dummy_signal_sell = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "signal": "SELL",
        "strength": "moderate_sell",
        "entry_price": 68000.75,
        "stop_loss": 68500.90,
        "take_profit_1": 67500.50,
        "take_profit_2": 67000.30,
        "take_profit_3": 66500.10,
        "risk_reward_ratio_base": "1:1.2",
        "reason": "EMA bearish, MACD bearish momentum, price reacted to bearish OB."
    }

    dummy_signal_no = {
        "symbol": "XRP/USDT",
        "timeframe": "1h",
        "signal": "NO_SIGNAL",
        "strength": "none",
        "entry_price": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "take_profit_3": None,
        "risk_reward_ratio_base": None,
        "reason": "Konfluensi belum cukup untuk sinyal valid."
    }

    print("\n--- Mengirim Sinyal BELI (Dummy) ---")
    send_signal_to_telegram(dummy_signal_buy)

    print("\n--- Mengirim Sinyal JUAL (Dummy) ---")
    send_signal_to_telegram(dummy_signal_sell)

    print("\n--- Mengirim Sinyal NO_SIGNAL (Dummy) ---")
    send_signal_to_telegram(dummy_signal_no)

    # Contoh langsung penggunaan kelas (jika Anda ingin menguji secara langsung)
    # bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    # chat_id = os.getenv("TELEGRAM_CHAT_ID")
    # if bot_token and chat_id:
    #     test_messenger = TelegramMessenger(bot_token=bot_token, chat_id=chat_id)
    #     test_messenger.send_message("Ini pesan uji langsung dari objek TelegramMessenger.")
