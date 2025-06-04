import asyncio
import json
import websockets
from utils.logger import setup_logger
from utils.config_loader import load_config
from database.influxdb_connector import write_to_influx
from datetime import datetime

# Setup logger dan konfigurasi
logger = setup_logger("ohlcv_streamer")
config = load_config()

# OKX WebSocket Config (Futures)
OKX_WS_URI = "wss://ws.okx.com:8443/ws/v5/public"
SYMBOL = "SOL-USDT-SWAP"         # ✅ Perpetual Futures
OKX_PAIR = SYMBOL
OKX_CHANNEL = "candles"          # ✅ PASTIKAN ini 'candles' (pakai S)
OKX_INTERVAL = "1m"              # ✅ Interval candle

async def stream_okx_ohlcv():
    logger.info(f"Connecting to OKX WebSocket at {OKX_WS_URI}")
    async for websocket in websockets.connect(OKX_WS_URI):
        try:
            # ✅ SUBSCRIBE MESSAGE BENAR
            sub_msg = {
                "op": "subscribe",
                "args": [{
                    "channel": OKX_CHANNEL,
                    "instId": SYMBOL,
                    "bar": OKX_INTERVAL
                }]
            }
            await websocket.send(json.dumps(sub_msg))
            logger.info(f"Subscribed to {OKX_CHANNEL} ({OKX_INTERVAL}) for {SYMBOL}")

            async for message in websocket:
                msg = json.loads(message)

                # Konfirmasi langganan
                if msg.get('event') == 'subscribe':
                    logger.info(f"Subscription confirmed: {msg.get('arg')}")
                    continue

                # ✅ Data candle masuk
                if 'data' in msg and \
                   msg.get('arg', {}).get('channel') == OKX_CHANNEL and \
                   msg.get('arg', {}).get('bar') == OKX_INTERVAL:
                    for candle in msg['data']:
                        if len(candle) < 6:
                            logger.warning(f"Incomplete candle data: {candle}")
                            continue

                        try:
                            ts = int(candle[0])
                            data = {
                                "timestamp": ts,
                                "open": float(candle[1]),
                                "high": float(candle[2]),
                                "low": float(candle[3]),
                                "close": float(candle[4]),
                                "volume": float(candle[5])
                            }

                            tags = {
                                "pair": OKX_PAIR,
                                "interval": OKX_INTERVAL,
                                "exchange": "OKX",
                                "instType": "SWAP"
                            }

                            dt = datetime.fromtimestamp(ts / 1000)
                            logger.info(
                                f"[{dt.strftime('%Y-%m-%d %H:%M')}] {SYMBOL} "
                                f"O:{data['open']:.4f} H:{data['high']:.4f} "
                                f"L:{data['low']:.4f} C:{data['close']:.4f} "
                                f"V:{data['volume']:.2f}"
                            )

                            write_to_influx("ohlcv", data, tags)

                        except Exception as e:
                            logger.error(f"Parse error: {e} | candle: {candle}")

                elif msg.get('event') == 'error':
                    logger.error(f"WebSocket error: {msg}")
                else:
                    logger.debug(f"Ignored message: {msg}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed: {e}. Reconnecting...")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)

        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(stream_okx_ohlcv())
    except KeyboardInterrupt:
        logger.info("Streamer stopped by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
