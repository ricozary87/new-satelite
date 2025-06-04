# utils/config_loader.py

import os
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    return {
        # EXCHANGE KEYS
        "BINANCE_API_KEY": os.getenv("BINANCE_API_KEY"),
        "BINANCE_SECRET_KEY": os.getenv("BINANCE_SECRET_KEY"),
        "OKX_API_KEY": os.getenv("OKX_API_KEY"),
        "OKX_SECRET_KEY": os.getenv("OKX_SECRET_KEY"),

        # RPC
        "SOLANA_RPC_URL": os.getenv("SOLANA_RPC_URL"),

        # INFLUXDB
        "INFLUXDB_HOST": os.getenv("INFLUXDB_HOST"),
        "INFLUXDB_PORT": os.getenv("INFLUXDB_PORT"),
        "INFLUXDB_TOKEN": os.getenv("INFLUXDB_TOKEN"),
        "INFLUXDB_ORG": os.getenv("INFLUXDB_ORG"),
        "INFLUXDB_BUCKET": os.getenv("INFLUXDB_BUCKET"),

        # REDIS
        "REDIS_HOST": os.getenv("REDIS_HOST"),
        "REDIS_PORT": os.getenv("REDIS_PORT"),
        "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD"),

        # TELEGRAM
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID")
    }
