import pandas as pd
from binance.client import Client
from binance.enums import HistoricalKlinesType

class BinanceCandleFetcher:
    def __init__(self, api_key: str, secret_key: str):
        self.client = Client(api_key, secret_key)

    def fetch_candles(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """
        Mengambil data candlestick (OHLCV) dari Binance.

        Args:
            symbol (str): Simbol trading (misal, 'BTCUSDT').
            interval (str): Interval waktu candle (misal, '1m', '5m', '1h', '1d').
            limit (int): Jumlah candle yang akan diambil. Max 1000 per request.

        Returns:
            pd.DataFrame: DataFrame yang berisi data OHLCV dengan kolom:
                          ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                          Timestamp akan menjadi index DataFrame.
        """
        try:
            # Menggunakan kline_type.SPOT untuk data spot
            klines = self.client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                kline_type=HistoricalKlineType.SPOT, # Pastikan ini disetel untuk spot trading
                limit=limit
            )

            if not klines:
                print(f"No klines data found for {symbol} on {interval}.")
                return pd.DataFrame()

            # Konversi data ke DataFrame
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Konversi kolom numerik ke tipe float
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Konversi open_time ke datetime dan atur sebagai index
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df = df.set_index('open_time')
            
            # Pilih kolom yang relevan dan urutkan
            df = df[['open', 'high', 'low', 'close', 'volume']]
            df = df.sort_index() # Pastikan data terurut berdasarkan waktu

            return df

        except Exception as e:
            print(f"Error fetching Binance candles for {symbol} - {interval}: {e}")
            return pd.DataFrame()

# Contoh penggunaan (untuk pengujian individual, bisa dihapus jika tidak diperlukan)
if __name__ == "__main__":
    # Ini hanya akan berjalan jika Anda menjalankan file ini secara langsung
    # Bukan saat diimpor oleh main.py
    # Pastikan Anda punya API Key dan Secret Key Binance yang valid di sini untuk tes
    # api_key = "YOUR_BINANCE_API_KEY"
    # secret_key = "YOUR_BINANCE_SECRET_KEY"

    # fetcher = BinanceCandleFetcher(api_key, secret_key)
    # data = fetcher.fetch_candles("BTCUSDT", "1h", limit=100)
    # if not data.empty:
    #     print("Data Binance berhasil diambil:")
    #     print(data.head())
    # else:
    #     print("Gagal mengambil data dari Binance.")
    pass # Biarkan pass jika tidak ingin menjalankan contoh di sini
