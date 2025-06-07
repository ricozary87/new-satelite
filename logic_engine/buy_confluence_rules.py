# File: logic_engine/buy_confluence_rules.py
# Tujuan: Berisi logika spesifik untuk mengecek konfluensi sinyal BELI.
# Telah disempurnakan untuk penggunaan helper functions dan threshold yang lebih jelas.

import logging
from .confluence_helpers import _is_price_in_zone, _is_price_near_zone, _is_price_entering_zone, safe_get_nested

logger = logging.getLogger(__name__)

# --- KONSTANTA AMBANG BATAS (Dapat dipindahkan ke config_loader nanti) ---
# Ambang batas untuk Funding Rate positif yang signifikan (bullish)
FUNDING_RATE_THRESHOLD_POSITIVE = 0.0001
# Ambang batas Open Interest yang tinggi (menunjukkan aktivitas pasar)
OPEN_INTEREST_HIGH_THRESHOLD = 100000000 # Contoh nilai ambang batas OI (sesuaikan dengan aset Anda)
# Multiplier untuk mendeteksi 'wall' di orderbook (volume = multiplier * harga_saat_ini)
ORDERBOOK_WALL_VOLUME_MULTIPLIER = 50 # Contoh: volume wall 50x harga saat ini
# Batas atas untuk rasio Long/Short yang dianggap bullish bias
LONG_SHORT_RATIO_BULLISH_BIAS_MAX = 1.05
# Batas bawah untuk rasio Long/Short yang dianggap bullish bias
LONG_SHORT_RATIO_BULLISH_BIAS_MIN = 0.95
# Ambang batas Taker Buy Volume yang dominan (lebih banyak beli)
TAKER_VOLUME_BULLISH_THRESHOLD = 0.55
# Toleransi persentase untuk harga mendekati Order Block
PRICE_NEAR_ZONE_TOLERANCE_OB = 0.005


def check_buy_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float, market_data_additional: dict) -> dict:
    """
    Menentukan sinyal BELI berdasarkan konfluensi antara indikator klasik, sinyal SMC,
    dan data pasar tambahan (orderbook, funding, OI, dll.).
    Mengembalikan dictionary dengan level kekuatan sinyal.
    """
    logger.debug("🧐 Mengecek kondisi beli...")
    signal_strength = {'type': 'no_signal', 'reason': []}

    # --- Ambil Data Indikator Klasik ---
    # Pastikan classic_indicators itu sendiri bukan None. Jika None, langsung kembalikan no_signal.
    if classic_indicators is None:
        logger.warning("Classic indicators data is None. Skipping classic indicator confluence check.")
        signal_strength['reason'].append("Classic Indicators: Data missing.")
        return signal_strength

    ema_signal = classic_indicators.get("ema_signal")
    macd_trend = classic_indicators.get("macd_trend")
    rsi_signal = classic_indicators.get("rsi_signal") # Tidak digunakan langsung di sini, tapi bisa untuk detail
    stoch_signal = classic_indicators.get("stoch_signal")
    bb_signal = classic_indicators.get("bb_signal")
    rsi_value = classic_indicators.get("rsi") # Nilai RSI untuk kondisi overbought/oversold
    
    # --- Ambil Data Sinyal SMC ---
    # Pastikan smc_signals itu sendiri bukan None. Jika None, gunakan dictionary kosong untuk mencegah error .get().
    if smc_signals is None:
        logger.warning("SMC signals data is None. Skipping SMC confluence check.")
        smc_signals_safe = {} # Jadikan dictionary kosong agar .get() tidak error
        signal_strength['reason'].append("SMC Signals: Data missing.")
    else:
        smc_signals_safe = smc_signals
        
    bos_choch = smc_signals_safe.get("bos_choch", {})
    fvg_data = smc_signals_safe.get("fvg", {})
    order_block_data = smc_signals_safe.get("order_block", {})
    eq_zone_data = smc_signals_safe.get("eq_zone", {})

    # --- Ambil Data Market Tambahan ---
    # Pastikan market_data_additional itu sendiri bukan None. Jika None, gunakan dictionary kosong.
    if market_data_additional is None:
        logger.warning("Additional market data is None. Skipping additional market data confluence check.")
        binance_spot_data = {}
        binance_futures_data = {}
        bybit_data = {}
        signal_strength['reason'].append("Additional Market Data: Data missing.")
    else:
        binance_spot_data = market_data_additional.get("binance_spot", {})
        binance_futures_data = market_data_additional.get("binance_futures", {})
        bybit_data = market_data_additional.get("bybit", {})

    # Inisialisasi status konfluensi untuk setiap kondisi bullish
    confluences = {
        'ema_bullish_trend': False, 'macd_bullish_momentum': False, 'rsi_not_overbought': False,
        'stoch_bullish_momentum': False, 'smc_structure_break': False, 'fvg_bullish_presence': False,
        'ob_bullish_presence': False, 'price_reacting_to_fvg': False, 'price_reacting_to_ob': False,
        'liquidity_grab_low': False, 'bb_bullish_signal': False,
        'ob_support_strong': False, 'funding_rate_bullish': False, 'oi_increasing_with_price': False,
        'long_short_ratio_bullish_divergence': False, 'taker_buy_volume_dominant': False
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bullish", "bullish"]:
        confluences['ema_bullish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bullish":
        confluences['macd_bullish_momentum'] = True
        signal_strength['reason'].append("MACD: Bullish Momentum")
    
    if rsi_value is not None and rsi_value < 70:
        confluences['rsi_not_overbought'] = True
        signal_strength['reason'].append(f"RSI: Not Overbought ({rsi_value:.2f})")
        if rsi_value < 30:
            signal_strength['reason'].append(f"RSI: Oversold ({rsi_value:.2f}) - Potential Reversal")
    
    if stoch_signal in ["bullish", "oversold_bullish_cross"]:
        confluences['stoch_bullish_momentum'] = True
        signal_strength['reason'].append("Stoch RSI: Bullish Momentum/Crossover")

    if bb_signal in ["cross_above_middle", "bounce_from_lower", "cross_above_lower_band", "outside_lower_band"]:
        confluences['bb_bullish_signal'] = True
        signal_strength['reason'].append(f"BB: {bb_signal.replace('_', ' ').title()}")

    # --- Evaluasi Sinyal SMC ---
    bos_type = bos_choch.get("type")
    if bos_type in ["bullish_bos", "bullish_choch", "bullish_choch_potential"]:
        confluences['smc_structure_break'] = True
        signal_strength['reason'].append(f"SMC: {bos_type.replace('_', ' ').title()} Detected")

    if fvg_data and fvg_data.get("type") == "bullish_fvg" and fvg_data.get("zone") and current_price is not None and current_open_price is not None:
        fvg_zone = fvg_data['zone']
        confluences['fvg_bullish_presence'] = True
        signal_strength['reason'].append("SMC: Bullish FVG Present")
        if _is_price_in_zone(current_price, fvg_zone) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_zone):
            confluences['price_reacting_to_fvg'] = True
            signal_strength['reason'].append("SMC: Price in/entering Bullish FVG (reaction)")

    bullish_ob_data = order_block_data.get("bullish_ob")
    if bullish_ob_data and bullish_ob_data.get('low') is not None and bullish_ob_data.get('high') is not None and current_price is not None and current_open_price is not None:
        ob_zone = [bullish_ob_data['low'], bullish_ob_data['high']]
        confluences['ob_bullish_presence'] = True
        signal_strength['reason'].append("SMC: Bullish OB Present")
        if _is_price_near_zone(current_price, ob_zone, tolerance_percent=PRICE_NEAR_ZONE_TOLERANCE_OB) or \
           _is_price_entering_zone(current_open_price, current_price, ob_zone):
            confluences['price_reacting_to_ob'] = True
            signal_strength['reason'].append("SMC: Price near/in/entering Bullish OB (reaction)")
            
    if eq_zone_data.get('eq_low') and len(eq_zone_data['eq_low']) > 0 and current_price is not None and current_open_price is not None:
        last_eq_low_level = max(eq_zone_data['eq_low'])
        if current_open_price < last_eq_low_level and current_price > last_eq_low_level and current_price < (last_eq_low_level * 1.005):
            confluences['liquidity_grab_low'] = True
            signal_strength['reason'].append(f"SMC: Equal Low ({last_eq_low_level:.2f}) swept and reversed (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_low_level, last_eq_low_level], tolerance_percent=0.001):
            confluences['liquidity_grab_low'] = True
            signal_strength['reason'].append(f"SMC: Price near Equal Low ({last_eq_low_level:.2f}) (potential liquidity).")

    # --- Evaluasi Data Market Tambahan untuk Sinyal BELI ---
    # Orderbook (Binance Spot) - Deteksi Dinding Beli (Strong Bid Wall)
    binance_orderbook = binance_spot_data.get("orderbook")
    if binance_orderbook and binance_orderbook.get('bids') and current_price is not None:
        # Pengecekan keamanan: pastikan list bids tidak kosong sebelum mengakses elemen
        if binance_orderbook['bids']:
            top_bids = sorted([float(b[0]) for b in binance_orderbook['bids']], reverse=True)
            top_bid_price = top_bids[0] if top_bids else 0
            
            if top_bid_price and (current_price - top_bid_price) / current_price < 0.005: # within 0.5%
                top_bid_volume = sum([float(b[1]) for b in binance_orderbook['bids'][:5]]) if len(binance_orderbook['bids']) >= 5 else sum([float(b[1]) for b in binance_orderbook['bids']])
                if top_bid_volume > ORDERBOOK_WALL_VOLUME_MULTIPLIER * current_price:
                    confluences['ob_support_strong'] = True
                    signal_strength['reason'].append("Orderbook: Strong Bid Wall / Support detected near current price.")
                    logger.debug(f"Strong Bid Wall Detected: {top_bid_volume:.2f} at {top_bid_price:.2f}")
                else:
                    logger.debug(f"Orderbook Bid Wall present but volume not strong enough: {top_bid_volume:.2f} vs required > {ORDERBOOK_WALL_VOLUME_MULTIPLIER * current_price:.2f}")
        else:
            logger.debug("Binance orderbook bids list is empty.")

    # Funding Rate (Binance Futures & Bybit) - Sentimen Bullish
    binance_fr = safe_get_nested(binance_futures_data, ['funding_rate', 0, 'fundingRate'], 0.0)
    bybit_fr = safe_get_nested(bybit_data, ['funding_rate', 'result', 'list', 0, 'fundingRate'], 0.0)

    if binance_fr > FUNDING_RATE_THRESHOLD_POSITIVE or bybit_fr > FUNDING_RATE_THRESHOLD_POSITIVE:
        confluences['funding_rate_bullish'] = True
        signal_strength['reason'].append("Funding Rate: Positive (Bullish Sentiment).")
        logger.debug(f"Funding Rates: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")
    elif binance_fr != 0.0 or bybit_fr != 0.0:
        logger.debug(f"Funding Rates not strongly bullish: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")


    # Open Interest (Binance Futures & Bybit) - OI Meningkat dengan Harga Naik
    binance_oi = safe_get_nested(binance_futures_data, ['open_interest', 'openInterest'], 0.0)
    bybit_oi = safe_get_nested(bybit_data, ['open_interest', 'result', 'list', 0, 'openInterest'], 0.0)

    # Logika: Jika harga naik (current > open) DAN OI di kedua bursa besar (indikasi uang baru masuk)
    if current_price is not None and current_open_price is not None and \
       current_price > current_open_price and \
       binance_oi > OPEN_INTEREST_HIGH_THRESHOLD and bybit_oi > OPEN_INTEREST_HIGH_THRESHOLD:
        confluences['oi_increasing_with_price'] = True
        signal_strength['reason'].append("Open Interest: Increasing with rising price (Bullish confirmation).")
        logger.debug(f"Open Interests: Binance {binance_oi}, Bybit {bybit_oi}")
    elif binance_oi > 0 or bybit_oi > 0:
        logger.debug(f"OI not indicating strong bullish trend: Binance {binance_oi}, Bybit {bybit_oi}. Price move: {current_price - current_open_price:.2f}")


    # Long/Short Ratio (Binance Futures & Bybit) - Kontrarian Bullish
    binance_ls_account_ratio = safe_get_nested(binance_futures_data, ['long_short_account_ratio', 0, 'longShortRatio'], 1.0)
    bybit_ls_result = bybit_data.get("long_short_ratio")
    bybit_ls_ratio = safe_get_nested(bybit_data, ['long_short_ratio', 'result', 'list', 0, 'longShortRatio'], 1.0)

    # Contoh: Jika rasio long/short mendekati 1.0 (seimbang) atau sedikit di bawah 1.0 dan mulai naik
    # Atau jika sudah sangat rendah (bearish ekstrem) dan berbalik naik
    if (binance_ls_account_ratio < LONG_SHORT_RATIO_BULLISH_BIAS_MAX and binance_ls_account_ratio > LONG_SHORT_RATIO_BULLISH_BIAS_MIN) or \
       (bybit_ls_ratio < LONG_SHORT_RATIO_BULLISH_BIAS_MAX and bybit_ls_ratio > LONG_SHORT_RATIO_BULLISH_BIAS_MIN):
        confluences['long_short_ratio_bullish_divergence'] = True
        signal_strength['reason'].append("Long/Short Ratio: Relatively balanced or slightly bullish bias.")
        logger.debug(f"Long/Short Ratios: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")
    else:
        logger.debug(f"Long/Short Ratios not strongly bullish biased: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")


    # Taker Buy/Sell Volume (Binance Futures) - Dominasi Taker Buy
    taker_buy_sell_ratio = safe_get_nested(binance_futures_data, ['taker_buy_sell_volume', 0, 'buySellRatio'], 0.5)
    if taker_buy_sell_ratio > TAKER_VOLUME_BULLISH_THRESHOLD: # Lebih banyak taker buy
        confluences['taker_buy_volume_dominant'] = True
        signal_strength['reason'].append(f"Taker Volume: Buy Volume Dominant ({taker_buy_sell_ratio:.2f} ratio).")
        logger.debug(f"Taker Buy/Sell Ratio: {taker_buy_sell_ratio:.2f}")
    else:
        logger.debug(f"Taker Buy/Sell Ratio not strongly bullish: {taker_buy_sell_ratio:.2f}")

    # --- Kombinasi Logika Konfluensi untuk Sinyal BELI ---
    # Sinyal Sangat Kuat (Strong Buy)
    # Membutuhkan tren bullish, momentum, struktur break, DAN reaksi di POI (OB/FVG),
    # Serta konfirmasi dari likuiditas atau BB, DAN minimal 2 dari sinyal tambahan.
    if (confluences['ema_bullish_trend'] and
        confluences['macd_bullish_momentum'] and
        confluences['rsi_not_overbought'] and 
        confluences['stoch_bullish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_low'] or confluences['bb_bullish_signal'])):
        
        additional_bullish_signals = sum([
            confluences['ob_support_strong'],
            confluences['funding_rate_bullish'],
            confluences['oi_increasing_with_price'],
            confluences['long_short_ratio_bullish_divergence'],
            confluences['taker_buy_volume_dominant']
        ])
        
        if additional_bullish_signals >= 2: # Setidaknya 2 sinyal tambahan
            signal_strength['type'] = 'strong_buy'
            signal_strength['reason'].append(f"Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB) + {additional_bullish_signals} additional bullish signals.")
            logger.debug("Strong Buy Signal Detected!")
            return signal_strength

    # Sinyal Kuat (Moderate Buy)
    # Membutuhkan tren bullish, struktur break, dan setidaknya satu momentum/BB positif,
    # PLUS reaksi di POI, ATAU likuiditas terambil, DAN minimal 1 dari sinyal tambahan.
    if (confluences['ema_bullish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bullish_momentum'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low'])):
        
        additional_bullish_signals = sum([
            confluences['ob_support_strong'],
            confluences['funding_rate_bullish'],
            confluences['oi_increasing_with_price'],
            confluences['long_short_ratio_bullish_divergence'],
            confluences['taker_buy_volume_dominant']
        ])

        if additional_bullish_signals >= 1: # Setidaknya 1 sinyal tambahan
            signal_strength['type'] = 'moderate_buy'
            signal_strength['reason'].append(f"Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction + {additional_bullish_signals} additional bullish signals.")
            logger.debug("Moderate Buy Signal Detected.")
            return signal_strength

    # Sinyal Potensial (Weak Buy / Entry Confirmation)
    # Membutuhkan reaksi di POI DENGAN momentum positif ATAU likuiditas terambil
    # ATAU jika ada 3+ sinyal tambahan yang kuat tanpa POI/SMC
    if (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_low']) and \
       (confluences['rsi_not_overbought'] or confluences['stoch_bullish_momentum'] or confluences['bb_bullish_signal']):
        signal_strength['type'] = 'potential_buy'
        signal_strength['reason'].append("Potential Confluence: Price reacting at POI/Liquidity with momentum/BB confirmation.")
        logger.debug("Potential Buy Signal Detected.")
        return signal_strength

    logger.debug("No Buy Signal based on current confluence.")
    return signal_strength

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n--- Menguji check_buy_confluence ---")

    # --- Skenario 1: BELI Kuat (Semua data lengkap) ---
    print("\n--- Skenario 1: BELI Kuat (Semua data lengkap) ---")
    mock_classic_indicators = {
        "ema_signal": "strong_bullish", "macd_trend": "bullish", "rsi": 55.0,
        "stoch_signal": "bullish", "bb_signal": "cross_above_middle"
    }
    mock_smc_signals = {
        "bos_choch": {"type": "bullish_choch"},
        "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
        "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": None},
        "eq_zone": {"eq_low": [180.0, 180.5], "eq_high": []}
    }
    mock_market_data_additional = {
        "binance_spot": {"orderbook": {"bids": [["192.9", "1000"], ["192.8", "500"]]}},
        "binance_futures": {
            "funding_rate": [{"fundingRate": "0.0003"}],
            "open_interest": {"openInterest": "1500000000"},
            "taker_buy_sell_volume": [{"buySellRatio": "0.65"}],
            "long_short_account_ratio": [{"longShortRatio": "0.98"}]
        },
        "bybit": {
            "funding_rate": {"result": {"list": [{"fundingRate": "0.0002"}]}},
            "open_interest": {"result": {"list": [{"openInterest": "1300000000"}]}},
            "long_short_ratio": {"result": {"list": [{"longShortRatio": "0.97"}]}}
        }
    }
    current_price_mock = 193.0
    current_open_price_mock = 191.0

    result_buy_strong = check_buy_confluence(
        mock_classic_indicators, mock_smc_signals, current_price_mock, current_open_price_mock, mock_market_data_additional
    )
    print(f"Hasil Skenario BELI Kuat: {result_buy_strong}")

    # --- Skenario 2: Classic Indicators adalah None ---
    print("\n--- Skenario 2: Classic Indicators adalah None ---")
    result_ci_none = check_buy_confluence(
        None, mock_smc_signals, current_price_mock, current_open_price_mock, mock_market_data_additional
    )
    print(f"Hasil Skenario CI None: {result_ci_none}")

    # --- Skenario 3: SMC Signals adalah None ---
    print("\n--- Skenario 3: SMC Signals adalah None ---")
    result_smc_none = check_buy_confluence(
        mock_classic_indicators, None, current_price_mock, current_open_price_mock, mock_market_data_additional
    )
    print(f"Hasil Skenario SMC None: {result_smc_none}")

    # --- Skenario 4: Additional Market Data adalah None ---
    print("\n--- Skenario 4: Additional Market Data adalah None ---")
    result_market_data_none = check_buy_confluence(
        mock_classic_indicators, mock_smc_signals, current_price_mock, current_open_price_mock, None
    )
    print(f"Hasil Skenario Market Data None: {result_market_data_none}")

    # --- Skenario 5: Harga adalah None (akan ditangani di evaluate_market_confluence) ---
    print("\n--- Skenario 5: Harga adalah None (akan ditangani di evaluate_market_confluence) ---")
    # Ini akan menyebabkan error jika tidak ditangani di fungsi pemanggil (evaluate_market_confluence)
    # Fungsi check_buy_confluence sendiri diasumsikan menerima harga valid.
    # Namun, karena ada pengecekan current_price is not None di dalam buy_confluence_rules,
    # beberapa bagian logika akan di-skip, tapi tidak akan crash karena 'NoneType' object.
    result_price_none = check_buy_confluence(
        mock_classic_indicators, mock_smc_signals, None, None, mock_market_data_additional
    )
    print(f"Hasil Skenario Harga None (dikelola internal): {result_price_none}")

