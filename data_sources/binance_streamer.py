import json
import asyncio
import websockets
import logging
from core.analyzer_entry import analyze_coin

# Konfigurasi logging agar lebih informatif
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Daftar coin (lowercase sesuai format Binance)
# Sesuaikan dengan pair yang ingin Anda pantau
PAIRS = [
    "solusdt",
    "rndrusdt",
    "tiausdt",
    "arkmusdt",
    # Tambahkan pair lain jika mau, pastikan format lowercase
]

# Build URL multi-stream Binance
def build_binance_url(pairs: list) -> str:
    """
    Membangun URL WebSocket untuk multi-stream kline 1 jam dari Binance.

    Args:
        pairs (list): Daftar string pasangan koin (misalnya, ["solusdt", "btcusdt"]).

    Returns:
        str: URL WebSocket Binance.
    """
    if not pairs:
        logging.warning("Daftar PAIRS kosong. Tidak ada stream yang akan dipantau.")
        return "wss://stream.binance.com:9443/stream?streams=" # URL kosong atau default
    streams = "/".join([f"{pair}@kline_1h" for pair in pairs])
    return f"wss://stream.binance.com:9443/stream?streams={streams}"

# Handle setiap pesan dari Binance
async def handle_message(message: str):
    """
    Menangani pesan yang diterima dari stream WebSocket Binance.
    Jika sebuah candle 1 jam tertutup, ia akan memicu fungsi analyze_coin.

    Args:
        message (str): Pesan JSON yang diterima dari Binance.
    """
    try:
        data = json.loads(message)
        # Pastikan kita mendapatkan data kline (k) dan event data (data)
        kline = data.get("data", {}).get("k", {})

        # Jika candle sudah close (selesai 1 jam)
        if kline.get("x"): # 'x' adalah indikator bahwa candle sudah close
            symbol = kline.get("s")  # e.g., SOLUSDT
            logging.info(f"✅ Candle 1H Closed: {symbol}")

            try:
                # Memanggil fungsi analisis untuk koin yang bersangkutan
                analyze_coin(symbol)
            except Exception as e:
                # Logging error jika analisis gagal
                logging.error(f"❌ Error saat analisa {symbol}: {e}", exc_info=True)
    except json.JSONDecodeError:
        logging.error(f"Pesan bukan JSON yang valid: {message}")
    except Exception as e:
        logging.error(f"Error tidak terduga saat menangani pesan: {e}", exc_info=True)


# Main loop listener WebSocket
async def listen_binance():
    """
    Memulai koneksi WebSocket ke Binance dan terus mendengarkan pesan.
    Mencoba menyambung kembali jika terjadi error koneksi.
    """
    url = build_binance_url(PAIRS)
    logging.info(f"🔌 Connecting to Binance WebSocket: {url}")

    while True: # Loop tak terbatas untuk menjaga koneksi tetap hidup
        try:
            async with websockets.connect(url) as ws:
                logging.info("⚡ Connection established.")
                while True: # Loop untuk menerima pesan
                    message = await ws.recv()
                    await handle_message(message)
        except websockets.exceptions.ConnectionClosedOK:
            logging.info("ℹ️ WebSocket connection closed gracefully. Attempting to reconnect...")
        except websockets.exceptions.ConnectionClosedError as e:
            logging.error(f"🔥 WebSocket connection closed with error: {e}. Attempting to reconnect in 5 seconds...", exc_info=True)
        except Exception as e:
            # Menangkap error umum lainnya, misalnya masalah jaringan
            logging.error(f"🔥 Unexpected WebSocket error: {e}. Attempting to reconnect in 5 seconds...", exc_info=True)
        finally:
            # Selalu menunggu sebelum mencoba menyambung kembali
            await asyncio.sleep(5)  # Retry delay

if __name__ == "__main__":
    try:
        logging.info("Starting Binance WebSocket listener...")
        asyncio.run(listen_binance())
    except KeyboardInterrupt:
        logging.info("🛑 Stopped by user. Exiting.")
    except Exception as e:
        logging.critical(f"A critical error occurred: {e}", exc_info=True)
