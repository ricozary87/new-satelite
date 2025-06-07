# File: logic_engine/confluence_helpers.py
# Tujuan: Berisi fungsi-fungsi helper umum untuk logika konfluensi.

import logging

logger = logging.getLogger(__name__)

def _is_price_in_zone(current_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah harga saat ini berada di dalam zona yang diberikan."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)
    return zone_min <= current_price <= zone_max

def _is_price_near_zone(current_price: float, zone: list, tolerance_percent: float = 0.001) -> bool:
    """Helper: Memeriksa apakah harga saat ini mendekati zona yang diberikan dalam toleransi."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)
    
    # Hitung toleransi absolut berdasarkan harga saat ini
    abs_tolerance = current_price * tolerance_percent 
    
    return (current_price >= (zone_min - abs_tolerance) and current_price <= (zone_max + abs_tolerance))

def _is_price_entering_zone(open_price: float, close_price: float, zone: list) -> bool:
    """Helper: Memeriksa apakah lilin saat ini masuk ke dalam zona dari luar."""
    if zone is None or len(zone) != 2:
        return False
    zone_min, zone_max = sorted(zone)

    # Lilin bullish masuk zona dari bawah (open di bawah, close di dalam/melalui)
    bullish_entry = (open_price < zone_min and close_price >= zone_min and close_price <= zone_max)

    # Lilin bearish masuk zona dari atas (open di atas, close di dalam/melalui)
    bearish_entry = (open_price > zone_max and close_price <= zone_max and close_price >= zone_min)
    
    return bullish_entry or bearish_entry

def safe_get_nested(data: dict, keys: list, default=None):
    """
    Mengakses nilai dari dictionary bersarang dengan aman.
    Contoh: safe_get_nested(data, ['result', 'list', 0, 'fundingRate'], 0.0)
    """
    current_data = data
    for i, key in enumerate(keys):
        if isinstance(current_data, dict):
            current_data = current_data.get(key)
        elif isinstance(current_data, list) and isinstance(key, int):
            if key < len(current_data):
                current_data = current_data[key]
            else:
                return default # Indeks list di luar batas
        else:
            return default # Tipe data tidak sesuai dengan kunci
        
        if current_data is None and i < len(keys) - 1:
            return default # Nilai None di tengah jalur
    return current_data if current_data is not None else default

# Untuk pengujian mandiri
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    print("--- Testing _is_price_in_zone ---")
    print(f"Price 100 in [90, 110]: {_is_price_in_zone(100, [90, 110])}") # True
    print(f"Price 80 in [90, 110]: {_is_price_in_zone(80, [90, 110])}")  # False

    print("\n--- Testing _is_price_near_zone ---")
    print(f"Price 100.05 near [100, 100] (0.1%): {_is_price_near_zone(100.05, [100, 100], 0.001)}") # True
    print(f"Price 100.2 near [100, 100] (0.1%): {_is_price_near_zone(100.2, [100, 100], 0.001)}") # False

    print("\n--- Testing _is_price_entering_zone ---")
    # Bullish entry
    print(f"Bullish entry (100 -> 105) into [102, 108]: {_is_price_entering_zone(100, 105, [102, 108])}") # True
    print(f"Bullish no entry (100 -> 101) into [102, 108]: {_is_price_entering_zone(100, 101, [102, 108])}") # False
    # Bearish entry
    print(f"Bearish entry (110 -> 105) into [102, 108]: {_is_price_entering_zone(110, 105, [102, 108])}") # True
    print(f"Bearish no entry (110 -> 111) into [102, 108]: {_is_price_entering_zone(110, 111, [102, 108])}") # False

    print("\n--- Testing safe_get_nested ---")
    dummy_data = {
        'a': {'b': {'c': 123}},
        'x': {'y': [{'z': 456}]},
        'p': None,
        'q': {'r': []}
    }
    print(f"safe_get_nested(a.b.c): {safe_get_nested(dummy_data, ['a', 'b', 'c'])}") # 123
    print(f"safe_get_nested(x.y.0.z): {safe_get_nested(dummy_data, ['x', 'y', 0, 'z'])}") # 456
    print(f"safe_get_nested(p.q): {safe_get_nested(dummy_data, ['p', 'q'])}") # None
    print(f"safe_get_nested(a.b.d): {safe_get_nested(dummy_data, ['a', 'b', 'd'])}") # None
    print(f"safe_get_nested(q.r.0): {safe_get_nested(dummy_data, ['q', 'r', 0])}") # None (list index out of bounds)
    print(f"safe_get_nested(x.y.1.z, default='empty'): {safe_get_nested(dummy_data, ['x', 'y', 1, 'z'], 'empty')}") # empty
