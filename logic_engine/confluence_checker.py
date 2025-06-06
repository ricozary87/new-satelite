# File: logic_engine/confluence_checker.py
# Tujuan: Mengevaluasi konfluensi sinyal pasar secara keseluruhan.
# Telah di-refactor untuk memisahkan logika beli dan jual ke modul terpisah
# dan menggunakan helper functions untuk keterbacaan dan pemeliharaan yang lebih baik.

import logging
# Import helper functions dari confluence_helpers.py
from .confluence_helpers import _is_price_in_zone, _is_price_near_zone, _is_price_entering_zone, safe_get_nested
# Import fungsi pengecekan beli dari buy_confluence_rules.py
from .buy_confluence_rules import check_buy_confluence
# Import fungsi pengecekan jual dari sell_confluence_rules.py
from .sell_confluence_rules import check_sell_confluence

logger = logging.getLogger(__name__)


def evaluate_market_confluence(market_data: dict) -> dict:
    """
    Mengevaluasi konfluensi keseluruhan berdasarkan indikator klasik, sinyal SMC,
    dan data pasar tambahan yang dikumpulkan.
    Ini adalah fungsi utama yang akan dipanggil dari modul lain (misalnya, analyzer_entry.py).

    Args:
        market_data (dict): Kamus berisi semua data pasar yang telah dikumpulkan
                            (classic_indicators, smc_signals, current_price, current_open_price,
                            market_data_additional, dll.).

    Returns:
        dict: Hasil analisis konfluensi, berisi 'overall_sentiment' dan 'signals' (daftar alasan).
    """
    logger.info("🔍 Mengevaluasi konfluensi sinyal dari semua data yang tersedia...")

    # --- Bagian 1: Ekstraksi dan Validasi Data ---
    classic_indicators = market_data.get("classic_indicators", {})
    smc_signals = market_data.get("smc_signals", {})
    current_price = market_data.get("current_price")
    current_open_price = market_data.get("current_open_price")
    market_data_additional = market_data.get("market_data_additional", {})

    # Pastikan data esensial tersedia
    if current_price is None or current_open_price is None:
        logger.error("Harga saat ini atau harga pembukaan tidak tersedia. Tidak dapat mengevaluasi konfluensi.")
        return {
            "overall_sentiment": "NO_DATA",
            "signals": ["Error: Missing current price data"]
        }

    # --- Bagian 2: Evaluasi Sinyal Beli dan Jual ---
    # Panggil fungsi cek beli dan jual dari modul terpisah, meneruskan data tambahan
    buy_strength_result = check_buy_confluence(classic_indicators, smc_signals, current_price, current_open_price, market_data_additional)
    sell_strength_result = check_sell_confluence(classic_indicators, smc_signals, current_price, current_open_price, market_data_additional)

    # --- Bagian 3: Resolusi Sinyal Akhir ---
    final_signal_type = 'NEUTRAL'
    final_reason_list = []

    buy_type = buy_strength_result.get('type', 'no_signal')
    sell_type = sell_strength_result.get('type', 'no_signal')

    # Logika Prioritas: Strong > Moderate > Potential. Hindari konflik strong.
    # Ini bisa disesuaikan lebih lanjut jika perlu hierarki yang lebih kompleks.
    
    # Check for Strongest, non-conflicting signals first
    if buy_type == 'strong_buy' and sell_type != 'strong_sell':
        final_signal_type = 'BULLISH'
        final_reason_list = buy_strength_result['reason']
        logger.info("Resolved: Strong Buy signal found.")
    elif sell_type == 'strong_sell' and buy_type != 'strong_buy':
        final_signal_type = 'BEARISH'
        final_reason_list = sell_strength_result['reason']
        logger.info("Resolved: Strong Sell signal found.")
    elif buy_type == 'strong_buy' and sell_type == 'strong_sell':
        # Konflik kuat, lebih baik tidak trading
        final_signal_type = 'CONFLICTING'
        final_reason_list.append("Conflicting strong buy and strong sell signals. Market uncertainty.")
        logger.warning("Resolved: Conflicting strong buy and strong sell signals. Setting to CONFLICTING.")
    # If no strong, non-conflicting signals, check for moderate
    elif buy_type == 'moderate_buy' and sell_type not in ['strong_sell', 'moderate_sell']:
        final_signal_type = 'BULLISH'
        final_reason_list = buy_strength_result['reason']
        logger.info("Resolved: Moderate Buy signal found.")
    elif sell_type == 'moderate_sell' and buy_type not in ['strong_buy', 'moderate_buy']:
        final_signal_type = 'BEARISH'
        final_reason_list = sell_strength_result['reason']
        logger.info("Resolved: Moderate Sell signal found.")
    elif buy_type == 'moderate_buy' and sell_type == 'moderate_sell':
        # Konflik moderate, lebih baik netral
        final_signal_type = 'NEUTRAL'
        final_reason_list.append("Conflicting moderate buy and moderate sell signals.")
        logger.warning("Resolved: Conflicting moderate buy and moderate sell signals. Setting to NEUTRAL.")
    # If no strong or moderate, non-conflicting signals, check for potential
    elif buy_type == 'potential_buy' and sell_type == 'no_signal':
        final_signal_type = 'NEUTRAL' # Potential signals might not be strong enough for a direct trade
        final_reason_list = buy_strength_result['reason']
        logger.info("Resolved: Potential Buy signal found, setting to NEUTRAL.")
    elif sell_type == 'potential_sell' and buy_type == 'no_signal':
        final_signal_type = 'NEUTRAL' # Potential signals might not be strong enough for a direct trade
        final_reason_list = sell_strength_result['reason']
        logger.info("Resolved: Potential Sell signal found, setting to NEUTRAL.")
    else:
        # Jika tidak ada sinyal yang jelas atau ada konflik level bawah
        final_signal_type = 'NEUTRAL'
        final_reason_list.append("No clear dominant confluence signal detected.")
        logger.info("Resolved: No clear dominant signal. Setting overall sentiment to NEUTRAL.")
    
    logger.info(f"Hasil Konfluensi Akhir: Sentimen: {final_signal_type}, Alasan: {final_reason_list}")
    
    # Mengembalikan dictionary sesuai dengan ekspektasi analyzer_entry.py
    return {
        "overall_sentiment": final_signal_type,
        "signals": final_reason_list # Menggunakan list sebagai alasan
    }

# Untuk pengujian mandiri
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n--- Menguji Confluence Checker ---")

    # --- Skenario BELI Kuat ---
    print("\n--- Skenario BELI Kuat ---")
    mock_data_buy_strong = {
        "classic_indicators": {
            "ema_signal": "strong_bullish", "macd_trend": "bullish", "rsi": 55.0,
            "stoch_signal": "bullish", "bb_signal": "cross_above_middle"
        },
        "smc_signals": {
            "bos_choch": {"type": "bullish_choch"},
            "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
            "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": None},
            "eq_zone": {"eq_low": [180.0, 180.5], "eq_high": []}
        },
        "current_price": 193.0,
        "current_open_price": 191.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [["192.9", "1000"], ["192.8", "500"]]}},
            "binance_futures": {
                "funding_rate": [{"fundingRate": "0.0003"}],
                "open_interest": {"openInterest": "1500000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.65"}]
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "0.0002"}]}},
                "open_interest": {"result": {"list": [{"openInterest": "1300000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "0.98"}]}}
            }
        }
    }
    result_buy_strong = evaluate_market_confluence(mock_data_buy_strong)
    print(f"Sinyal BELI Kuat: {result_buy_strong}")

    # --- Skenario JUAL Kuat ---
    print("\n--- Skenario JUAL Kuat ---")
    mock_data_sell_strong = {
        "classic_indicators": {
            "ema_signal": "strong_bearish", "macd_trend": "bearish", "rsi": 45.0,
            "stoch_signal": "bearish", "bb_signal": "cross_below_middle"
        },
        "smc_signals": {
            "bos_choch": {"type": "bearish_choch"},
            "fvg": {"type": "bearish_fvg", "zone": [205.0, 210.0]},
            "order_block": {"bullish_ob": None, "bearish_ob": {"low": 208.0, "high": 212.0}},
            "eq_zone": {"eq_low": [], "eq_high": [220.0, 220.5]}
        },
        "current_price": 207.0,
        "current_open_price": 209.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"asks": [["207.1", "1200"], ["207.2", "600"]]}},
            "binance_futures": {
                "funding_rate": [{"fundingRate": "-0.0002"}],
                "open_interest": {"openInterest": "1600000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.35"}]
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "-0.0003"}]}},
                "open_interest": {"result": {"list": [{"openInterest": "1400000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "1.15"}]}}
            }
        }
    }
    result_sell_strong = evaluate_market_confluence(mock_data_sell_strong)
    print(f"Sinyal JUAL Kuat: {result_sell_strong}")

    # --- Skenario NETRAL (No Signal) ---
    print("\n--- Skenario NETRAL (No Signal) ---")
    mock_data_neutral = {
        "classic_indicators": {
            "ema_signal": "neutral", "macd_trend": "neutral", "rsi": 50.0,
            "stoch_signal": "neutral", "bb_signal": "normal"
        },
        "smc_signals": {
            "bos_choch": {"type": "no_break"}, "fvg": {}, "order_block": {}, "eq_zone": {}
        },
        "current_price": 100.0,
        "current_open_price": 100.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [], "asks": []}},
            "binance_futures": {"funding_rate": [], "open_interest": {}, "taker_buy_sell_volume": []},
            "bybit": {"funding_rate": {"result": {"list": []}}, "open_interest": {"result": {"list": []}}, "long_short_ratio": {"result": {"list": []}}}
        }
    }
    result_neutral = evaluate_market_confluence(mock_data_neutral)
    print(f"Sinyal NETRAL: {result_neutral}")

    # --- Skenario Konflik (Strong Buy dan Strong Sell) ---
    print("\n--- Skenario Konflik (Strong Buy dan Strong Sell) ---")
    mock_data_conflicting = {
        "classic_indicators": {
            "ema_signal": "strong_bullish", "macd_trend": "bullish", "rsi": 55.0,
            "stoch_signal": "bullish", "bb_signal": "cross_above_middle"
        },
        "smc_signals": {
            "bos_choch": {"type": "bullish_choch"},
            "fvg": {"type": "bullish_fvg", "zone": [190.0, 195.0]},
            "order_block": {"bullish_ob": {"low": 188.0, "high": 192.0}, "bearish_ob": {"low": 196.0, "high": 199.0}},
            "eq_zone": {"eq_low": [180.0], "eq_high": [200.0]}
        },
        "current_price": 193.0,
        "current_open_price": 191.0,
        "market_data_additional": {
            "binance_spot": {"orderbook": {"bids": [["192.9", "1000"]], "asks": [["193.1", "1200"]]}},
            "binance_futures": {
                "funding_rate": [{"fundingRate": "0.0003"}],
                "open_interest": {"openInterest": "1500000000"},
                "taker_buy_sell_volume": [{"buySellRatio": "0.65"}]
            },
            "bybit": {
                "funding_rate": {"result": {"list": [{"fundingRate": "-0.0003"}]}},
                "open_interest": {"result": {"list": [{"openInterest": "1400000000"}]}},
                "long_short_ratio": {"result": {"list": [{"longShortRatio": "1.15"}]}}
            }
        }
    }
    result_conflicting = evaluate_market_confluence(mock_data_conflicting)
    print(f"Sinyal KONFLIK: {result_conflicting}")
