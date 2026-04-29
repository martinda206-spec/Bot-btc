import time
import requests
import pandas as pd

# ================= CONFIG =================

TELEGRAM_BOT_TOKEN = "PEGA"
TELEGRAM_CHAT_ID = "2123346158"

BASE_URL = "https://fapi.binance.com"

SYMBOL = "BTCUSDT"  # 🔥 CORREGIDO
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
    except:
        pass


def get_klines():
    url = BASE_URL + "/fapi/v1/klines"

    r = requests.get(
        url,
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
        "time","open","high","low","close","volume",
        "ct","qv","trades","tb","tq","ig"
    ])

    df[["open","high","low","close","volume"]] = df[
        ["open","high","low","close","volume"]
    ].astype(float)

    df["ema25"] = df["close"].ewm(span=EMA_FAST).mean()
    df["ema50"] = df["close"].ewm(span=EMA_MID).mean()
    df["ema99"] = df["close"].ewm(span=EMA_SLOW).mean()
    df["vol_ma"] = df["volume"].rolling(VOL_MA).mean()

    return df


def check_signal():
    df = get_klines()
    c = df.iloc[-2]

    close = c["close"]
    open_ = c["open"]
    volume = c["volume"]

    ema25 = c["ema25"]
    ema50 = c["ema50"]
    ema99 = c["ema99"]
    vol_ma = c["vol_ma"]

    candle_time = int(c["time"])

    near = (
        abs(close - ema25)/close < PULLBACK_DISTANCE or
        abs(close - ema50)/close < PULLBACK_DISTANCE
    )

    vol_ok = volume > vol_ma

    if ema25 > ema50 and close > ema99 and close > open_ and near and vol_ok:
        return {
            "type": "🟢 LONG",
            "entry": close,
            "tp": close * (1 + TAKE_PROFIT_PCT),
            "sl": close * (1 - STOP_LOSS_PCT),
            "time": candle_time
        }

    if ema25 < ema50 and close < ema99 and close < open_ and near and vol_ok:
        return {
            "type": "🔴 SHORT",
            "entry": close,
            "tp": close * (1 - TAKE_PROFIT_PCT),
            "sl": close * (1 + STOP_LOSS_PCT),
            "time": candle_time
        }


def format_msg(s):
    return (
        f"📊 <b>SEÑAL {SYMBOL}</b>\n\n"
        f"{s['type']}\n"
        f"Entrada: {s['entry']:.2f}\n"
        f"TP: {s['tp']:.2f}\n"
        f"SL: {s['sl']:.2f}\n\n"
        f"⏱ 15m"
    )


def main():
    global last_signal_time

    send_telegram(f"🤖 Bot activo ({SYMBOL})")

    while True:
        try:
            signal = check_signal()

            if signal and signal["time"] != last_signal_time:
                msg = format_msg(signal)
                print(msg)
                send_telegram(msg)
                last_signal_time = signal["time"]
            else:
                print("Sin señal...")

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            err = f"⚠️ Error:\n{e}"
            print(err)
            send_telegram(err)
            time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
