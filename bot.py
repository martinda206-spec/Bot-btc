import os
import time
import requests
import pandas as pd

# ================= CONFIG =================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2123346158")

BASE_URL = "https://api.binance.com"

SYMBOL = "BTCUSDT"
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        print("Error enviando Telegram:", e)


def get_klines():
    url = BASE_URL + "/api/v3/klines"

    r = requests.get(
        url,
        params={
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "limit": 150
        },
        headers={
            "User-Agent": "Mozilla/5.0"
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

    open_price = candle["open"]
    close = candle["close"]
    volume = candle["volume"]

    ema25 = candle["ema25"]
    ema50 = candle["ema50"]
    ema99 = candle["ema99"]
    vol_ma = candle["vol_ma"]

    candle_time = int(candle["time"])

    near_ema = (
        abs(close - ema25) / close <= PULLBACK_DISTANCE or
        abs(close - ema50) / close <= PULLBACK_DISTANCE
    )

    volume_ok = volume > vol_ma

    bullish = close > open_price
    bearish = close < open_price

    long_signal = (
        ema25 > ema50 and
        close > ema99 and
        bullish and
        near_ema and
        volume_ok
    )

    short_signal = (
        ema25 < ema50 and
        close < ema99 and
        bearish and
        near_ema and
        volume_ok
    )

    if long_signal:
        entry = close
        tp = entry * (1 + TAKE_PROFIT_PCT)
        sl = entry * (1 - STOP_LOSS_PCT)

        return {
            "type": "🟢 COMPRA / LONG",
            "entry": entry,
            "tp": tp,
            "sl": sl,
            "time": candle_time
        }

    if short_signal:
        entry = close
        tp = entry * (1 - TAKE_PROFIT_PCT)
        sl = entry * (1 + STOP_LOSS_PCT)

        return {
            "type": "🔴 VENTA / SHORT",
            "entry": entry,
            "tp": tp,
            "sl": sl,
            "time": candle_time
        }

    return None


def format_signal(signal):
    return (
        f"📊 <b>SEÑAL {SYMBOL}</b>\n\n"
        f"Tipo: <b>{signal['type']}</b>\n"
        f"Entrada: <b>{signal['entry']:.2f}</b>\n"
        f"Take Profit: <b>{signal['tp']:.2f}</b>\n"
        f"Stop Loss: <b>{signal['sl']:.2f}</b>\n\n"
        f"⏱ Temporalidad: {INTERVAL}\n"
        f"📈 Estrategia: EMA25 / EMA50 / EMA99 + Volumen"
    )


def main():
    global last_signal_time

    print("Bot de señales iniciado")
    send_telegram(f"🤖 Bot de señales iniciado\nPar: {SYMBOL}\nTemporalidad: {INTERVAL}")

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
            error_msg = f"⚠️ Error en bot:\n{e}"
            print(error_msg)
            send_telegram(error_msg)
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
