import time
import requests
import pandas as pd
from datetime import datetime

# ================= CONFIG =================

TELEGRAM_TOKEN = "8581404343:AAHCAZh6f0V55MBRtH1knrlR-1z23sDIWM0"
CHAT_ID = "TU_CHAT_ID_AQUI"

SYMBOL = "BTCUSDT"
INTERVAL = "15"   # Bybit usa "15" no "15m"
LIMIT = 200

TP_TREND = 0.004
SL_TREND = 0.0025

TP_RANGE = 0.003
SL_RANGE = 0.0025

MAX_DISTANCE_FROM_SIGNAL = 0.0015

SLEEP_TIME = 60

last_signal = None

# ================= TELEGRAM =================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Error Telegram:", e)

# ================= BYBIT =================

def get_klines():
    url = "https://api.bybit.com/v5/market/kline"

    params = {
        "category": "linear",
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()["result"]["list"]

    data.reverse()

    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume", "turnover"
    ])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df

# ================= INDICADORES =================

def add_indicators(df):
    df["ema25"] = df["close"].ewm(span=25).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema99"] = df["close"].ewm(span=99).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()

    df["range_high"] = df["high"].rolling(40).max()
    df["range_low"] = df["low"].rolling(40).min()

    df["ema_spread"] = (
        abs(df["ema25"] - df["ema50"]) +
        abs(df["ema50"] - df["ema99"])
    ) / df["close"]

    return df

# ================= DETECCIÓN =================

def detect_market(df):
    last = df.iloc[-1]

    ema_flat = last["ema_spread"] < 0.004
    range_size = (last["range_high"] - last["range_low"]) / last["close"]

    if ema_flat and range_size < 0.025:
        return "RANGO"

    if last["ema25"] > last["ema50"] > last["ema99"]:
        return "TENDENCIA_ALCISTA"

    if last["ema25"] < last["ema50"] < last["ema99"]:
        return "TENDENCIA_BAJISTA"

    return "NEUTRAL"

# ================= FILTROS =================

def breakout_filter(df):
    last = df.iloc[-1]
    return last["volume"] > last["vol_ma"] * 2

def anti_fomo_filter(df, signal):
    _, entry, _, _, _ = signal
    last_price = df.iloc[-1]["close"]
    distance = abs(last_price - entry) / entry
    return distance <= MAX_DISTANCE_FROM_SIGNAL

# ================= SEÑALES =================

def trend_signal(df, market):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["volume"] > last["vol_ma"]:

        if market == "TENDENCIA_ALCISTA":
            if prev["close"] < prev["ema25"] and last["close"] > last["ema25"]:
                entry = last["close"]
                return "LONG", entry, entry*(1+TP_TREND), entry*(1-SL_TREND), "Tendencia"

        if market == "TENDENCIA_BAJISTA":
            if prev["close"] > prev["ema25"] and last["close"] < last["ema25"]:
                entry = last["close"]
                return "SHORT", entry, entry*(1-TP_TREND), entry*(1+SL_TREND), "Tendencia"

    return None

def range_signal(df):
    last = df.iloc[-1]

    high = last["range_high"]
    low = last["range_low"]
    price = last["close"]

    margin = (high - low) * 0.18

    if price <= low + margin:
        return "LONG", price, price*(1+TP_RANGE), price*(1-SL_RANGE), "Soporte"

    if price >= high - margin:
        return "SHORT", price, price*(1-TP_RANGE), price*(1+SL_RANGE), "Resistencia"

    return None

# ================= MENSAJE =================

def format_signal(signal, market):
    side, entry, tp, sl, strategy = signal
    emoji = "🟢" if side == "LONG" else "🔴"

    return f"""
📊 SEÑAL BTC

{emoji} {side}
Entrada: {entry:.2f}
TP: {tp:.2f}
SL: {sl:.2f}

Mercado: {market}
Estrategia: {strategy}

🛡 Anti-FOMO activo
"""

# ================= BOT =================

def run_bot():
    global last_signal

    send_telegram("🚀 BOT BTC SCALPING activo (Bybit)")

    while True:
        try:
            df = add_indicators(get_klines())
            market = detect_market(df)

            if breakout_filter(df):
                print("Ruptura fuerte - no operar")
                time.sleep(SLEEP_TIME)
                continue

            signal = None

            if market == "RANGO":
                signal = range_signal(df)
            else:
                signal = trend_signal(df, market)

            if signal:
                if not anti_fomo_filter(df, signal):
                    print("Anti-FOMO bloqueó señal")
                    time.sleep(SLEEP_TIME)
                    continue

                msg = format_signal(signal, market)
                send_telegram(msg)
                print(msg)

            else:
                print(datetime.now(), "Sin señal", market)

        except Exception as e:
            print("Error:", e)
            send_telegram(f"⚠️ Error del bot:\n{e}")

        time.sleep(SLEEP_TIME)

# ================= START =================

run_bot()
