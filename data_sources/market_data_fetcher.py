# File: data_sources/market_data_fetcher.py
# Tujuan: Menggabungkan semua endpoint GRATIS dari Binance & Bybit untuk data real-time maksimal
# Ini adalah versi yang diperluas dari file sebelumnya, dengan penambahan endpoint Binance Futures dan Bybit.

import requests
import time
import logging

# Konfigurasi logging untuk pesan kesalahan
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =========================
# KONFIGURASI UMUM
# =========================
# Base URL untuk API Binance Spot
BINANCE_SPOT_BASE_URL = "https://api.binance.com"
# Base URL untuk API Binance Futures
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
# Base URL untuk API Bybit (V5)
BYBIT_BASE_URL = "https://api.bybit.com"

# Default timeout untuk permintaan HTTP
REQUEST_TIMEOUT = 10 # Detik

# =========================
# HELPER FUNCTIONS
# =========================

def _make_request(url: str, params: dict = None, headers: dict = None) -> dict or None:
    """
    Fungsi pembantu untuk melakukan permintaan HTTP GET dan menangani kesalahan umum.
    """
    try:
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Akan memunculkan HTTPError untuk status kode 4xx/5xx

        # Mengembalikan JSON jika sukses
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - URL: {url} - Response: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error occurred: {conn_err} - URL: {url}")
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error occurred: {timeout_err} - URL: {url}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"An unexpected error occurred: {req_err} - URL: {url}")
    except ValueError as json_err: # JSONDecodeError mewarisi dari ValueError
        logging.error(f"Failed to decode JSON response: {json_err} - URL: {url} - Response: {response.text}")
    return None # Kembalikan None jika ada kesalahan

# =========================
# BINANCE SPOT SECTION
# =========================

def fetch_binance_spot_orderbook(symbol: str, limit: int = 100) -> dict or None:
    """
    Mengambil data order book dari Binance Spot.
    Dokumentasi: https://binance-docs.github.io/apidocs/spot/en/#order-book
    Maksimal limit: 1000
    """
    url = f"{BINANCE_SPOT_BASE_URL}/api/v3/depth"
    params = {"symbol": symbol.upper(), "limit": limit}
    logging.info(f"Fetching Binance Spot orderbook for {symbol} with limit {limit}")
    return _make_request(url, params=params)

def fetch_binance_spot_aggtrades(symbol: str, limit: int = 50) -> dict or None:
    """
    Mengambil agregasi data perdagangan (trades) dari Binance Spot.
    Dokumentasi: https://binance-docs.github.io/apidocs/spot/en/#compressed-aggregate-trades-list
    Maksimal limit: 1000
    """
    url = f"{BINANCE_SPOT_BASE_URL}/api/v3/aggTrades"
    params = {"symbol": symbol.upper(), "limit": limit}
    logging.info(f"Fetching Binance Spot aggTrades for {symbol} with limit {limit}")
    return _make_request(url, params=params)

def fetch_binance_spot_24h_stats(symbol: str) -> dict or None:
    """
    Mengambil statistik harga 24 jam untuk simbol tertentu dari Binance Spot.
    Dokumentasi: https://binance-docs.github.io/apidocs/spot/en/#24hr-ticker-price-change-statistics
    """
    url = f"{BINANCE_SPOT_BASE_URL}/api/v3/ticker/24hr"
    params = {"symbol": symbol.upper()}
    logging.info(f"Fetching Binance Spot 24hr stats for {symbol}")
    return _make_request(url, params=params)

def fetch_binance_spot_klines(symbol: str, interval: str = "1m", limit: int = 500) -> list or None:
    """
    Mengambil data candlestick (kline) dari Binance Spot.
    Dokumentasi: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
    Interval: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
    Maksimal limit: 1000
    """
    url = f"{BINANCE_SPOT_BASE_URL}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    logging.info(f"Fetching Binance Spot klines for {symbol} interval {interval} with limit {limit}")
    return _make_request(url, params=params)

def fetch_binance_spot_exchange_info() -> dict or None:
    """
    Mengambil informasi pertukaran Binance Spot, termasuk daftar simbol dan aturan perdagangan.
    Dokumentasi: https://binance-docs.github.io/apidocs/spot/en/#exchange-information
    """
    url = f"{BINANCE_SPOT_BASE_URL}/api/v3/exchangeInfo"
    logging.info("Fetching Binance Spot exchange information")
    return _make_request(url)

# =========================
# BINANCE FUTURES SECTION
# =========================

def fetch_binance_futures_funding_rate(symbol: str, limit: int = 1) -> dict or None:
    """
    Mengambil data Funding Rate dari Binance Futures.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#get-funding-rate-history
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/fundingRate"
    params = {"symbol": symbol.upper(), "limit": limit}
    logging.info(f"Fetching Binance Futures Funding Rate for {symbol} with limit {limit}")
    return _make_request(url, params=params)

def fetch_binance_futures_open_interest(symbol: str) -> dict or None:
    """
    Mengambil data Open Interest dari Binance Futures.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#open-interest
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/openInterest"
    params = {"symbol": symbol.upper()}
    logging.info(f"Fetching Binance Futures Open Interest for {symbol}")
    return _make_request(url, params=params)

def fetch_binance_futures_long_short_account_ratio(symbol: str, period: str = '5m', limit: int = 1) -> list or None:
    """
    Mengambil data Top Trader Long/Short Ratio (Akun) dari Binance Futures.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#top-trader-long-short-ratio-accounts
    Period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/topLongShortAccountRatio"
    params = {"symbol": symbol.upper(), "period": period, "limit": limit}
    logging.info(f"Fetching Binance Futures Top Long/Short Account Ratio for {symbol} period {period}")
    return _make_request(url, params=params)

def fetch_binance_futures_long_short_position_ratio(symbol: str, period: str = '5m', limit: int = 1) -> list or None:
    """
    Mengambil data Top Trader Long/Short Ratio (Posisi) dari Binance Futures.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#top-trader-long-short-ratio-positions
    Period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/topLongShortPositionRatio"
    params = {"symbol": symbol.upper(), "period": period, "limit": limit}
    logging.info(f"Fetching Binance Futures Top Long/Short Position Ratio for {symbol} period {period}")
    return _make_request(url, params=params)

def fetch_binance_futures_taker_buy_sell_volume(symbol: str, period: str = '5m', limit: int = 1) -> list or None:
    """
    Mengambil data Taker Buy/Sell Volume dari Binance Futures.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#taker-buy-sell-volume
    Period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/takerBuySellVol"
    params = {"symbol": symbol.upper(), "period": period, "limit": limit}
    logging.info(f"Fetching Binance Futures Taker Buy/Sell Volume for {symbol} period {period}")
    return _make_request(url, params=params)

def fetch_binance_futures_exchange_info() -> dict or None:
    """
    Mengambil informasi pertukaran Binance Futures, termasuk daftar simbol dan aturan perdagangan.
    Dokumentasi: https://binance-docs.github.io/apidocs/futures/en/#exchange-information
    """
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/exchangeInfo"
    logging.info("Fetching Binance Futures exchange information")
    return _make_request(url)

# =========================
# BYBIT SECTION (V5)
# =========================

def fetch_bybit_orderbook(symbol: str, limit: int = 50) -> dict or None:
    """
    Mengambil data order book dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/orderbook
    Kategori: linear, inverse, spot, option
    Maksimal limit: 50 (linear/inverse), 200 (spot), 25 (option)
    """
    url = f"{BYBIT_BASE_URL}/v5/market/orderbook"
    params = {"category": "linear", "symbol": symbol.upper(), "limit": limit}
    logging.info(f"Fetching Bybit orderbook for {symbol} (linear) with limit {limit}")
    return _make_request(url, params=params)

def fetch_bybit_funding_rate(symbol: str) -> dict or None:
    """
    Mengambil riwayat funding rate dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/funding-history
    """
    url = f"{BYBIT_BASE_URL}/v5/market/funding/history"
    params = {"category": "linear", "symbol": symbol.upper(), "limit": 1}
    logging.info(f"Fetching Bybit funding rate for {symbol} (linear)")
    return _make_request(url, params=params)

def fetch_bybit_open_interest(symbol: str, interval_time: int = 60) -> dict or None:
    """
    Mengambil data open interest dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/open-interest
    Interval waktu: 5, 15, 30, 60, 240, 720 (menit)
    """
    url = f"{BYBIT_BASE_URL}/v5/market/open-interest"
    params = {"category": "linear", "symbol": symbol.upper(), "intervalTime": interval_time}
    logging.info(f"Fetching Bybit open interest for {symbol} (linear) with interval {interval_time} mins")
    return _make_request(url, params=params)

def fetch_bybit_tickers(symbol: str) -> dict or None:
    """
    Mengambil data ticker (harga terkini, volume, dll.) dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/tickers
    """
    url = f"{BYBIT_BASE_URL}/v5/market/tickers"
    params = {"category": "linear", "symbol": symbol.upper()}
    logging.info(f"Fetching Bybit tickers for {symbol} (linear)")
    return _make_request(url, params=params)

def fetch_bybit_kline(symbol: str, interval: str = "1", limit: int = 200) -> dict or None:
    """
    Mengambil data candlestick (kline) dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/kline
    Interval: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, M, W
    Maksimal limit: 1000
    """
    url = f"{BYBIT_BASE_URL}/v5/market/kline"
    params = {"category": "linear", "symbol": symbol.upper(), "interval": interval, "limit": limit}
    logging.info(f"Fetching Bybit kline for {symbol} (linear) interval {interval} with limit {limit}")
    return _make_request(url, params=params)

def fetch_bybit_recent_trade_list(symbol: str, limit: int = 10) -> dict or None:
    """
    Mengambil daftar perdagangan terbaru dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/recent-trade
    Maksimal limit: 1000
    """
    url = f"{BYBIT_BASE_URL}/v5/market/recent-trade"
    params = {"category": "linear", "symbol": symbol.upper(), "limit": limit}
    logging.info(f"Fetching Bybit recent trade list for {symbol} (linear) with limit {limit}")
    return _make_request(url, params=params)

def fetch_bybit_long_short_ratio(symbol: str, period: str = '5min', limit: int = 1) -> dict or None:
    """
    Mengambil data rasio long/short dari Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/long-short-ratio
    Period: 5min, 15min, 30min, 1h, 4h, 1d
    """
    url = f"{BYBIT_BASE_URL}/v5/market/long-short-ratio"
    params = {"category": "linear", "symbol": symbol.upper(), "period": period, "limit": limit}
    logging.info(f"Fetching Bybit long/short ratio for {symbol} (linear) period {period}")
    return _make_request(url, params=params)

def fetch_bybit_exchange_info(category: str = "linear", symbol: str = None) -> dict or None:
    """
    Mengambil informasi instrumen/pertukaran Bybit (V5).
    Dokumentasi: https://bybit-exchange.github.io/docs/v5/market/instruments-info
    Kategori: linear, inverse, spot, option
    Jika symbol tidak diberikan, akan mengembalikan info untuk semua instrumen dalam kategori.
    """
    url = f"{BYBIT_BASE_URL}/v5/market/instruments-info"
    params = {"category": category}
    if symbol:
        params["symbol"] = symbol.upper()
        logging.info(f"Fetching Bybit exchange information for {symbol} (category: {category})")
    else:
        logging.info(f"Fetching Bybit exchange information for category: {category}")
    return _make_request(url, params=params)

# =========================
# TESTING (Manual)
# =========================
if __name__ == '__main__':
    spot_symbol = "BTCUSDT"
    futures_symbol = "BTCUSDT" # Biasanya sama untuk BTCUSDT
    print(f"\n--- Testing data fetching for Spot: {spot_symbol}, Futures: {futures_symbol} ---")

    print("\n=== Binance Spot Orderbook ===")
    binance_spot_ob = fetch_binance_spot_orderbook(spot_symbol, limit=5)
    if binance_spot_ob:
        print(f"Bids: {binance_spot_ob.get('bids')[:3]}...")
        print(f"Asks: {binance_spot_ob.get('asks')[:3]}...")
    time.sleep(0.5)

    print("\n=== Binance Futures Funding Rate ===")
    binance_futures_fr = fetch_binance_futures_funding_rate(futures_symbol)
    if binance_futures_fr and binance_futures_fr[0]:
        print(f"Latest Funding Rate: {binance_futures_fr[0].get('fundingRate')}")
    time.sleep(0.5)

    print("\n=== Binance Futures Open Interest ===")
    binance_futures_oi = fetch_binance_futures_open_interest(futures_symbol)
    if binance_futures_oi:
        print(f"Open Interest: {binance_futures_oi.get('openInterest')}")
    time.sleep(0.5)

    print("\n=== Binance Futures Top Long/Short Account Ratio (5m) ===")
    binance_futures_lsar = fetch_binance_futures_long_short_account_ratio(futures_symbol, period='5m')
    if binance_futures_lsar and binance_futures_lsar[0]:
        print(f"Long/Short Account Ratio: {binance_futures_lsar[0].get('longShortRatio')}")
    time.sleep(0.5)

    print("\n=== Binance Futures Top Long/Short Position Ratio (5m) ===")
    binance_futures_lspr = fetch_binance_futures_long_short_position_ratio(futures_symbol, period='5m')
    if binance_futures_lspr and binance_futures_lspr[0]:
        print(f"Long/Short Position Ratio: {binance_futures_lspr[0].get('longShortRatio')}")
    time.sleep(0.5)

    print("\n=== Binance Futures Taker Buy/Sell Volume (5m) ===")
    binance_futures_tbsv = fetch_binance_futures_taker_buy_sell_volume(futures_symbol, period='5m')
    if binance_futures_tbsv and binance_futures_tbsv[0]:
        print(f"Buy Volume: {binance_futures_tbsv[0].get('buySellRatio')}") # Rasio buy/sell
    time.sleep(0.5)

    print("\n=== Binance Spot Exchange Info (Partial) ===")
    binance_spot_info = fetch_binance_spot_exchange_info()
    if binance_spot_info:
        print(f"Total symbols: {len(binance_spot_info.get('symbols', []))}")
        # print(binance_spot_info.get('symbols')[0]) # Contoh satu simbol
    time.sleep(0.5)

    print("\n=== Binance Futures Exchange Info (Partial) ===")
    binance_futures_info = fetch_binance_futures_exchange_info()
    if binance_futures_info:
        print(f"Total futures symbols: {len(binance_futures_info.get('symbols', []))}")
        # print(binance_futures_info.get('symbols')[0]) # Contoh satu simbol
    time.sleep(0.5)


    print("\n=== Bybit Orderbook ===")
    bybit_ob = fetch_bybit_orderbook(spot_symbol, limit=5)
    if bybit_ob and bybit_ob.get('result') and bybit_ob['result'].get('list'):
        print(f"Bids: {bybit_ob['result']['list'][0].get('bids')[:3]}...")
        print(f"Asks: {bybit_ob['result']['list'][0].get('asks')[:3]}...")
    time.sleep(0.5)

    print("\n=== Bybit Recent Trade List ===")
    bybit_recent_trades = fetch_bybit_recent_trade_list(spot_symbol, limit=3)
    if bybit_recent_trades and bybit_recent_trades.get('result') and bybit_recent_trades['result'].get('list'):
        print(f"First trade: {bybit_recent_trades['result']['list'][0]}")
    time.sleep(0.5)

    print("\n=== Bybit Long/Short Ratio (5min) ===")
    bybit_lsr = fetch_bybit_long_short_ratio(futures_symbol, period='5min')
    if bybit_lsr and bybit_lsr.get('result') and bybit_lsr['result'].get('list'):
        print(f"Long/Short Ratio: {bybit_lsr['result']['list'][0].get('longShortRatio')}")
    time.sleep(0.5)

    print("\n=== Bybit Exchange Info (Partial) ===")
    bybit_exchange_info = fetch_bybit_exchange_info(category="linear")
    if bybit_exchange_info and bybit_exchange_info.get('result') and bybit_exchange_info['result'].get('list'):
        print(f"Total instruments (linear): {len(bybit_exchange_info['result'].get('list', []))}")
        # print(bybit_exchange_info['result']['list'][0]) # Contoh satu instrumen
    time.sleep(0.5)

    print("\n--- Testing complete ---")   
