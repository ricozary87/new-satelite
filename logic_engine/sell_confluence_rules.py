# File: logic_engine/sell_confluence_rules.py
# Tujuan: Berisi logika spesifik untuk mengecek konfluensi sinyal JUAL.
# Telah disempurnakan untuk penggunaan helper functions dan threshold yang lebih jelas.

import logging
from .confluence_helpers import _is_price_in_zone, _is_price_near_zone, _is_price_entering_zone, safe_get_nested

logger = logging.getLogger(__name__)

# --- KONSTANTA AMBANG BATAS (Dapat dipindahkan ke config_loader nanti) ---
# Ambang batas untuk Funding Rate negatif yang signifikan (bearish)
FUNDING_RATE_THRESHOLD_NEGATIVE = -0.0001
# Ambang batas Open Interest yang tinggi (menunjukkan aktivitas pasar)
OPEN_INTEREST_HIGH_THRESHOLD = 100000000 # Contoh nilai ambang batas OI (sesuaikan dengan aset Anda)
# Multiplier untuk mendeteksi 'wall' di orderbook (volume = multiplier * harga_saat_ini)
ORDERBOOK_WALL_VOLUME_MULTIPLIER = 50 # Contoh: volume wall 50x harga saat ini
# Batas bawah untuk rasio Long/Short yang dianggap bearish bias
LONG_SHORT_RATIO_BEARISH_BIAS_MIN = 1.10
# Batas atas untuk rasio Long/Short yang dianggap bearish bias (untuk menghindari ekstrem)
LONG_SHORT_RATIO_BEARISH_BIAS_MAX = 1.25
# Ambang batas Taker Sell Volume yang dominan (lebih banyak jual)
TAKER_VOLUME_BEARISH_THRESHOLD = 0.45
# Toleransi persentase untuk harga mendekati Order Block
PRICE_NEAR_ZONE_TOLERANCE_OB = 0.005


def check_sell_confluence(classic_indicators: dict, smc_signals: dict, current_price: float, current_open_price: float, market_data_additional: dict) -> dict:
    """
    Menentukan sinyal JUAL berdasarkan konfluensi antara indikator klasik, sinyal SMC,
    dan data pasar tambahan (orderbook, funding, OI, dll.).
    Mengembalikan dictionary dengan level kekuatan sinyal.
    """
    logger.debug("🧐 Mengecek kondisi jual...")
    signal_strength = {'type': 'no_signal', 'reason': []}

    # --- Ambil Data Indikator Klasik ---
    ema_signal = classic_indicators.get("ema_signal")
    macd_trend = classic_indicators.get("macd_trend")
    rsi_signal = classic_indicators.get("rsi_signal") # Tidak digunakan langsung di sini, tapi bisa untuk detail
    stoch_signal = classic_indicators.get("stoch_signal")
    bb_signal = classic_indicators.get("bb_signal")
    rsi_value = classic_indicators.get("rsi") # Nilai RSI untuk kondisi overbought/oversold

    # --- Ambil Data Sinyal SMC ---
    bos_choch = smc_signals.get("bos_choch", {})
    fvg_data = smc_signals.get("fvg", {})
    order_block_data = smc_signals.get("order_block", {})
    eq_zone_data = smc_signals.get("eq_zone", {})

    # --- Ambil Data Market Tambahan ---
    binance_spot_data = market_data_additional.get("binance_spot", {})
    binance_futures_data = market_data_additional.get("binance_futures", {})
    bybit_data = market_data_additional.get("bybit", {})

    # Inisialisasi status konfluensi untuk setiap kondisi bearish
    confluences = {
        'ema_bearish_trend': False,
        'macd_bearish_momentum': False,
        'rsi_not_oversold': False, # Ini berarti RSI tidak di bawah 30 (normal/overbought)
        'stoch_bearish_momentum': False,
        'smc_structure_break': False,
        'fvg_bearish_presence': False,
        'ob_bearish_presence': False,
        'price_reacting_to_fvg': False,
        'price_reacting_to_ob': False,
        'liquidity_grab_high': False,
        'bb_bearish_signal': False,
        # Sinyal dari data market tambahan
        'ob_resistance_strong': False,
        'funding_rate_bearish': False,
        'oi_increasing_with_price_drop': False,
        'long_short_ratio_bearish_divergence': False,
        'taker_sell_volume_dominant': False
    }

    # --- Evaluasi Indikator Klasik ---
    if ema_signal in ["strong_bearish", "bearish"]:
        confluences['ema_bearish_trend'] = True
        signal_strength['reason'].append(f"EMA: {ema_signal.replace('_', ' ').title()} Trend")
    
    if macd_trend == "bearish":
        confluences['macd_bearish_momentum'] = True
        signal_strength['reason'].append("MACD: Bearish Momentum")
    
    # RSI: Tidak oversold dan di bawah level overbought
    if rsi_value is not None and rsi_value > 30: # Tidak oversold (bisa normal atau overbought)
        confluences['rsi_not_oversold'] = True
        signal_strength['reason'].append(f"RSI: Not Oversold ({rsi_value:.2f})")
        if rsi_value > 70: # Tambahan detail jika overbought (potensi reversal ke bawah)
            signal_strength['reason'].append(f"RSI: Overbought ({rsi_value:.2f}) - Potential Reversal")
    
    if stoch_signal in ["bearish", "overbought_bearish_cross"]:
        confluences['stoch_bearish_momentum'] = True
        signal_strength['reason'].append("Stoch RSI: Bearish Momentum/Crossover")

    if bb_signal in ["cross_below_middle", "bounce_from_upper", "cross_below_upper_band", "outside_upper_band"]:
        confluences['bb_bearish_signal'] = True
        signal_strength['reason'].append(f"BB: {bb_signal.replace('_', ' ').title()}")

    # --- Evaluasi Sinyal SMC ---
    bos_type = bos_choch.get("type")
    if bos_type in ["bearish_bos", "bearish_choch", "bearish_choch_potential"]:
        confluences['smc_structure_break'] = True
        signal_strength['reason'].append(f"SMC: {bos_type.replace('_', ' ').title()} Detected")

    if fvg_data and fvg_data.get("type") == "bearish_fvg" and fvg_data.get("zone"):
        fvg_zone = fvg_data['zone']
        confluences['fvg_bearish_presence'] = True
        signal_strength['reason'].append("SMC: Bearish FVG Present")
        # Harga bereaksi: saat ini di dalam FVG, atau baru masuk ke FVG
        if _is_price_in_zone(current_price, fvg_zone) or \
           _is_price_entering_zone(current_open_price, current_price, fvg_zone):
            confluences['price_reacting_to_fvg'] = True
            signal_strength['reason'].append("SMC: Price in/entering Bearish FVG (reaction)")

    bearish_ob_data = order_block_data.get("bearish_ob")
    if bearish_ob_data and bearish_ob_data.get('low') is not None and bearish_ob_data.get('high') is not None:
        ob_zone = [bearish_ob_data['low'], bearish_ob_data['high']]
        confluences['ob_bearish_presence'] = True
        signal_strength['reason'].append("SMC: Bearish OB Present")
        # Harga bereaksi: saat ini di dekat/dalam OB, atau baru masuk ke OB
        if _is_price_near_zone(current_price, ob_zone, tolerance_percent=PRICE_NEAR_ZONE_TOLERANCE_OB) or \
           _is_price_entering_zone(current_open_price, current_price, ob_zone):
            confluences['price_reacting_to_ob'] = True
            signal_strength['reason'].append("SMC: Price near/in/entering Bearish OB (reaction)")
            
    if eq_zone_data.get('eq_high') and len(eq_zone_data['eq_high']) > 0:
        last_eq_high_level = min(eq_zone_data['eq_high']) # Ambil equal high yang paling rendah/terbaru
        # Jika lilin menembus equal high dan kemudian close di bawahnya (reversal)
        if current_open_price > last_eq_high_level and current_price < last_eq_high_level and current_price > (last_eq_high_level * 0.995): # Close sedikit di bawah
            confluences['liquidity_grab_high'] = True
            signal_strength['reason'].append(f"SMC: Equal High ({last_eq_high_level:.2f}) swept and reversed (liquidity grab).")
        elif _is_price_near_zone(current_price, [last_eq_high_level, last_eq_high_level], tolerance_percent=0.001):
            confluences['liquidity_grab_high'] = True # Masih di dekatnya, potensi penarikan
            signal_strength['reason'].append(f"SMC: Price near Equal High ({last_eq_high_level:.2f}) (potential liquidity).")

    # --- Evaluasi Data Market Tambahan untuk Sinyal JUAL ---
    # Orderbook (Binance Spot) - Deteksi Dinding Jual (Strong Ask Wall)
    binance_orderbook = binance_spot_data.get("orderbook")
    if binance_orderbook and binance_orderbook.get('asks') and current_price is not None:
        top_asks = sorted([float(a[0]) for a in binance_orderbook['asks']])
        top_ask_price = top_asks[0] if top_asks else float('inf')

        # Cek apakah ada ask yang sangat besar di dekat harga saat ini
        if current_price and top_ask_price and (top_ask_price - current_price) / current_price < 0.005: # within 0.5%
            top_ask_volume = sum([float(a[1]) for a in binance_orderbook['asks'][:5]]) # Sum volume 5 ask teratas
            if top_ask_volume > ORDERBOOK_WALL_VOLUME_MULTIPLIER * current_price: # Contoh ambang batas volume
                confluences['ob_resistance_strong'] = True
                signal_strength['reason'].append("Orderbook: Strong Ask Wall / Resistance detected near current price.")
                logger.debug(f"Strong Ask Wall Detected: {top_ask_volume:.2f} at {top_ask_price:.2f}")
            else:
                logger.debug(f"Orderbook Ask Wall present but volume not strong enough: {top_ask_volume:.2f} vs required > {ORDERBOOK_WALL_VOLUME_MULTIPLIER * current_price:.2f}")

    # Funding Rate (Binance Futures & Bybit) - Sentimen Bearish
    binance_fr = safe_get_nested(binance_futures_data, ['funding_rate', 0, 'fundingRate'], 0.0)
    bybit_fr = safe_get_nested(bybit_data, ['funding_rate', 'result', 'list', 0, 'fundingRate'], 0.0)

    if binance_fr < FUNDING_RATE_THRESHOLD_NEGATIVE or bybit_fr < FUNDING_RATE_THRESHOLD_NEGATIVE:
        confluences['funding_rate_bearish'] = True
        signal_strength['reason'].append("Funding Rate: Negative (Bearish Sentiment).")
        logger.debug(f"Funding Rates: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")
    elif binance_fr != 0.0 or bybit_fr != 0.0:
        logger.debug(f"Funding Rates not strongly bearish: Binance {binance_fr:.5f}, Bybit {bybit_fr:.5f}")

    # Open Interest (Binance Futures & Bybit) - OI Meningkat dengan Harga Turun
    binance_oi = safe_get_nested(binance_futures_data, ['open_interest', 'openInterest'], 0.0)
    bybit_oi = safe_get_nested(bybit_data, ['open_interest', 'result', 'list', 0, 'openInterest'], 0.0)

    # Logika: Jika harga turun (current < open) DAN OI di kedua bursa besar (indikasi uang baru masuk ke short)
    if current_price is not None and current_open_price is not None and \
       current_price < current_open_price and \
       binance_oi > OPEN_INTEREST_HIGH_THRESHOLD and bybit_oi > OPEN_INTEREST_HIGH_THRESHOLD:
        confluences['oi_increasing_with_price_drop'] = True
        signal_strength['reason'].append("Open Interest: Increasing with falling price (Bearish confirmation).")
        logger.debug(f"Open Interests: Binance {binance_oi}, Bybit {bybit_oi}")
    elif binance_oi > 0 or bybit_oi > 0:
        logger.debug(f"OI not indicating strong bearish trend: Binance {binance_oi}, Bybit {bybit_oi}. Price move: {current_price - current_open_price:.2f}")

    # Long/Short Ratio (Binance Futures & Bybit) - Kontrarian Bearish
    binance_ls_account_ratio = safe_get_nested(binance_futures_data, ['long_short_account_ratio', 0, 'longShortRatio'], 1.0)
    bybit_ls_result = bybit_data.get("long_short_ratio")
    bybit_ls_ratio = safe_get_nested(bybit_data, ['long_short_ratio', 'result', 'list', 0, 'longShortRatio'], 1.0)

    # Contoh: Jika rasio long/short sangat tinggi (misal > 1.1) yang bisa menjadi sinyal reversal (sell)
    # Atau jika sudah sangat tinggi dan mulai menunjukkan penurunan (divergensi bearish)
    if (binance_ls_account_ratio > LONG_SHORT_RATIO_BEARISH_BIAS_MIN or bybit_ls_ratio > LONG_SHORT_RATIO_BEARISH_BIAS_MIN) and \
       (binance_ls_account_ratio < LONG_SHORT_RATIO_BEARISH_BIAS_MAX and bybit_ls_ratio < LONG_SHORT_RATIO_BEARISH_BIAS_MAX):
        confluences['long_short_ratio_bearish_divergence'] = True
        signal_strength['reason'].append("Long/Short Ratio: Relatively high long bias or starting to decrease (Bearish sentiment).")
        logger.debug(f"Long/Short Ratios: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")
    else:
        logger.debug(f"Long/Short Ratios not strongly bearish biased: Binance {binance_ls_account_ratio:.2f}, Bybit {bybit_ls_ratio:.2f}")

    # Taker Buy/Sell Volume (Binance Futures) - Dominasi Taker Sell
    taker_buy_sell_ratio = safe_get_nested(binance_futures_data, ['taker_buy_sell_volume', 0, 'buySellRatio'], 0.5)
    if taker_buy_sell_ratio < TAKER_VOLUME_BEARISH_THRESHOLD: # Lebih banyak taker sell
        confluences['taker_sell_volume_dominant'] = True
        signal_strength['reason'].append(f"Taker Volume: Sell Volume Dominant ({taker_buy_sell_ratio:.2f} ratio).")
        logger.debug(f"Taker Buy/Sell Ratio: {taker_buy_sell_ratio:.2f}")
    else:
        logger.debug(f"Taker Buy/Sell Ratio not strongly bearish: {taker_buy_sell_ratio:.2f}")

    # --- Kombinasi Logika Konfluensi untuk Sinyal JUAL ---
    # Sinyal Sangat Kuat (Strong Sell)
    # Membutuhkan tren bearish, momentum, struktur break, DAN reaksi di POI (OB/FVG),
    # Serta konfirmasi dari likuiditas atau BB, DAN minimal 2 dari sinyal tambahan.
    if (confluences['ema_bearish_trend'] and
        confluences['macd_bearish_momentum'] and
        confluences['rsi_not_oversold'] and # RSI tidak oversold (bisa normal atau overbought)
        confluences['stoch_bearish_momentum'] and
        confluences['smc_structure_break'] and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg']) and
        (confluences['liquidity_grab_high'] or confluences['bb_bearish_signal'])):
        
        additional_bearish_signals = sum([
            confluences['ob_resistance_strong'],
            confluences['funding_rate_bearish'],
            confluences['oi_increasing_with_price_drop'],
            confluences['long_short_ratio_bearish_divergence'],
            confluences['taker_sell_volume_dominant']
        ])
        
        if additional_bearish_signals >= 2: # Setidaknya 2 sinyal tambahan
            signal_strength['type'] = 'strong_sell'
            signal_strength['reason'].append(f"Strong Confluence: All major conditions met (Trend, Momentum, Structure Break, POI reaction, Liquidity/BB) + {additional_bearish_signals} additional bearish signals.")
            logger.debug("Strong Sell Signal Detected!")
            return signal_strength

    # Sinyal Kuat (Moderate Sell)
    # Membutuhkan tren bearish, struktur break, dan setidaknya satu momentum/BB positif,
    # PLUS reaksi di POI, ATAU likuiditas terambil, DAN minimal 1 dari sinyal tambahan.
    if (confluences['ema_bearish_trend'] and
        confluences['smc_structure_break'] and
        (confluences['macd_bearish_momentum'] or confluences['stoch_bearish_momentum'] or confluences['bb_bearish_signal']) and
        (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_high'])):
        
        additional_bearish_signals = sum([
            confluences['ob_resistance_strong'],
            confluences['funding_rate_bearish'],
            confluences['oi_increasing_with_price_drop'],
            confluences['long_short_ratio_bearish_divergence'],
            confluences['taker_sell_volume_dominant']
        ])

        if additional_bearish_signals >= 1: # Setidaknya 1 sinyal tambahan
            signal_strength['type'] = 'moderate_sell'
            signal_strength['reason'].append(f"Moderate Confluence: Trend, Structure, Momentum/BB alignment, with POI/Liquidity interaction + {additional_bearish_signals} additional bearish signals.")
            logger.debug("Moderate Sell Signal Detected.")
            return signal_strength

    # Sinyal Potensial (Weak Sell / Entry Confirmation)
    # Membutuhkan reaksi di POI DENGAN momentum positif ATAU likuiditas terambil
    # ATAU jika ada 3+ sinyal tambahan yang kuat tanpa POI/SMC
    if (confluences['price_reacting_to_ob'] or confluences['price_reacting_to_fvg'] or confluences['liquidity_grab_high']) and \
       (confluences['rsi_not_oversold'] or confluences['stoch_bearish_momentum'] or confluences['bb_bearish_signal']):
        signal_strength['type'] = 'potential_sell'
        signal_strength['reason'].append("Potential Confluence: Price reacting at POI/Liquidity with momentum/BB confirmation.")
        logger.debug("Potential Sell Signal Detected.")
        return signal_strength

    logger.debug("No Sell Signal based on current confluence.")
    return signal_strength
