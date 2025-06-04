# === FILE: outputs/telegram_messenger.py ===
import requests # Pastikan Anda sudah menginstal library 'requests' (pip install requests)

class TelegramMessenger:
    """
    Kelas untuk mengirim pesan ke Telegram melalui Bot API.
    """
    def __init__(self, bot_token: str, chat_id: str):
        if not bot_token or not chat_id:
            print("Peringatan: Telegram BOT_TOKEN atau CHAT_ID tidak ditemukan. Pesan tidak akan terkirim.")
            self.bot_token = None
            self.chat_id = None
            self.base_url = None
        else:
            self.bot_token = bot_token
            self.chat_id = chat_id
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            print(f"Telegram Messenger siap. Chat ID: {self.chat_id}")

    def send_message(self, message: str):
        """
        Mengirim pesan teks ke chat Telegram yang ditentukan.

        Args:
            message (str): Pesan yang akan dikirim.
        """
        if not self.bot_token or not self.chat_id:
            print("❌ Telegram Messenger tidak dikonfigurasi. Pesan tidak terkirim.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML" # Mengizinkan format HTML seperti <b>, <i>
        }
        try:
            response = requests.post(self.base_url, data=payload)
            response.raise_for_status() # Akan menimbulkan HTTPError untuk status kode 4xx/5xx
            print("✅ Pesan Telegram berhasil dikirim.")
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error saat mengirim pesan Telegram: {e}")
            print(f"Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection Error saat mengirim pesan Telegram: {e}")
        except Exception as e:
            print(f"❌ Error tidak dikenal saat mengirim pesan Telegram: {e}")

# Contoh penggunaan (untuk pengujian mandiri file ini)
if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Pastikan Anda memiliki variabel ini di file .env Anda
    test_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    test_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if test_bot_token and test_chat_id:
        print("\nTesting Telegram Messenger:")
        test_messenger = TelegramMessenger(bot_token=test_bot_token, chat_id=test_chat_id)
        # Kirim pesan uji
        test_messenger.send_message("<b>Halo!</b> Ini adalah pesan uji dari bot trading Anda. Jika Anda melihat ini, integrasi Telegram berhasil!")
    else:
        print("Untuk menguji Telegram Messenger, pastikan TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID diatur di file .env Anda.")
