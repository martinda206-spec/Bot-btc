import os
import time
import requests
import pandas as pd

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2123346158")

BASE_URL = "https://data-api.binance.vision"

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


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Falta TELEGRAM_BOT_TOKEN")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
    except Exception as e:
        print("Error Telegram:", e)


def get_klines():
    r = requests.get(
        BASE_URL + "/api/v3/klines",
        params={
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "limit": 150
        },
        headers={"User-Agent": "Mozilla/5.0"},
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

    if ema25 > ema50 and close > ema99 and close > open_price and near_ema and volume_ok:
        entry = close
        return {
            "type": "🟢 COMPRA / LONG",
            "entry": entry,
            "tp": entry * (1 + TAKE_PROFIT_PCT),
            "sl": entry * (1 - STOP_LOSS_PCT),
            "time": candle_time
        }

    if ema25 < ema50 and close < ema99 and close < open_price and near_ema and volume_ok:
        entry = close
        return {
            "type": "🔴 VENTA / SHORT",
            "entry": entry,
            "tp": entry * (1 - TAKE_PROFIT_PCT),
            "sl": entry * (1 + STOP_LOSS_PCT),
            "time": candle_time
        }

    return None


def format_signal(signal):
    return (
        f"📊 <b>SEÑAL {SYMBOL}</b>\n\n"
        f"Tipo: <b>{signal['type']}</b>\n"
        f"Entrada: <b>{signal['entry']:.2f}</b>\n"
        f"TP: <b>{signal['tp']:.2f}</b>\n"
        f"SL: <b>{signal['sl']:.2f}</b>\n\n"
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
            print("Error en bot:", e)
            send_telegram(f"⚠️ Error en bot:\n{e}")
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
