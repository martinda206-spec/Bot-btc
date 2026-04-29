 # bot_senales_btcusdc_telegram.py

import time
import requests
import pandas as pd

# ================= CONFIG =================

TELEGRAM_BOT_TOKEN = "8581404343:AAHCAZh6f0V55MBRtH1knrlR-1z23sDIWM0"
TELEGRAM_CHAT_ID = "2123346158"

BASE_URL = "https://fapi.binance.com"

SYMBOL = "BTCUSDC"
INTERVAL = "15m"

EMA_FAST = 25
EMA_MID = 50
EMA_SLOW = 99
VOL_MA = 20

PULLBACK_DISTANCE = 0.002
STOP_LOSS_PCT = 0.0025
TAKE_PROFIT_PCT = 0.0040

SLEEP_SECONDS = 60

last_signal_time = None

# ==========================================


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Falta TELEGRAM_BOT_TOKEN")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print("Error Telegram:", e)


def get_klines():
    r = requests.get(
        BASE_URL + "/fapi/v1/klines",
        params={
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "limit": 150
        },
        timeout=10
    )
    r.raise_for_status()

    data = r.json()

    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    df[["open", "high", "low", "close", "volume"]] = df[
        ["open", "high", "low", "close", "volume"]
    ].astype(float)

    df["ema25"] = df["close"].ewm(span=EMA_FAST).mean()
    df["ema50"] = df["close"].ewm(span=EMA_MID).mean()
    df["ema99"] = df["close"].ewm(span=EMA_SLOW).mean()
    df["vol_ma"] = df["volume"].rolling(VOL_MA).mean()

    return df


def check_signal():
    df = get_klines()

    candle = df.iloc[-2]

    open_ = candle["open"]
    close = candle["close"]
    volume = candle["volume"]

    ema25 = candle["ema25"]
    ema50 = candle["ema50"]
    ema99 = candle["ema99"]
    vol_ma = candle["vol_ma"]

    candle_time = int(candle["time"])

    near = (
        abs(close - ema25) / close <= PULLBACK_DISTANCE or
        abs(close - ema50) / close <= PULLBACK_DISTANCE
    )

    volume_ok = volume > vol_ma

    bullish = close > open_
    bearish = close < open_

    if ema25 > ema50 and close > ema99 and bullish and near and volume_ok:
        entry = close
        return {
            "type": "🟢 COMPRA / LONG",
            "entry": entry,
            "tp": entry * (1 + TAKE_PROFIT_PCT),
            "sl": entry * (1 - STOP_LOSS_PCT),
            "time": candle_time
        }

    if ema25 < ema50 and close < ema99 and bearish and near and volume_ok:
        entry = close
        return {
            "type": "🔴 VENTA / SHORT",
            "entry": entry,
            "tp": entry * (1 - TAKE_PROFIT_PCT),
            "sl": entry * (1 + STOP_LOSS_PCT),
            "time": candle_time
        }

    return None


def format_signal(s):
    return (
        f"📊 <b>SEÑAL BTCUSDC</b>\n\n"
        f"Tipo: <b>{s['type']}</b>\n"
        f"Entrada: <b>{s['entry']:.1f}</b>\n"
        f"TP: <b>{s['tp']:.1f}</b>\n"
        f"SL: <b>{s['sl']:.1f}</b>\n\n"
        f"⏱ 15m | EMA + Volumen"
    )


def main():
    global last_signal_time

    print("Bot de señales iniciado")
    send_telegram("🤖 Bot de señales BTCUSDC iniciado")

    while True:
        try:
            signal = check_signal()

            if signal and signal["time"] != last_signal_time:
                msg = format_signal(signal)
                print(msg)
                send_telegram(msg)
                last_signal_time = signal["time"]
            else:
                print("Sin señal nueva...")

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            err = f"⚠️ Error:\n{e}"
            print(err)
            send_telegram(err)
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()           
