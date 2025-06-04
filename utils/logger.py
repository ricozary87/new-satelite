# utils/logger.py

import logging
import os

def setup_logger(name: str, log_level=logging.INFO, log_file=None):
    """
    Mengatur logger dengan nama, level, dan opsi output ke konsol dan/atau file.

    Args:
        name (str): Nama logger (biasanya __name__ dari modul).
        log_level (int): Level logging (e.g., logging.INFO, logging.DEBUG).
        log_file (str, optional): Path ke file log. Jika None, hanya output ke konsol.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Bersihkan handler yang sudah ada untuk mencegah duplikasi
    if logger.handlers:
        for handler in logger.handlers[:]: # Iterasi pada salinan list untuk modifikasi aman
            logger.removeHandler(handler)

    # StreamHandler untuk konsol
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # FileHandler untuk file log (opsional)
    if log_file:
        # Pastikan direktori log ada
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        fh = logging.FileHandler(log_file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

# Contoh penggunaan (bisa dihapus atau dijadikan contoh di modul lain)
if __name__ == "__main__":
    # Inisialisasi logger utama
    main_logger = setup_logger("main_app", log_level=logging.DEBUG, log_file="app.log")
    main_logger.info("Aplikasi dimulai.")
    main_logger.debug("Ini adalah pesan debug.")

    # Logger untuk modul spesifik
    data_logger = setup_logger("data_sources.ohlcv_streamer")
    data_logger.info("Memulai streaming OHLCV.")
