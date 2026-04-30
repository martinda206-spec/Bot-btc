import time
import requests
import pandas as pd
from datetime import datetime

# ================= CONFIGURACIÓN =================

TELEGRAM_TOKEN = "TU_TOKEN_AQUI"
CHAT_ID = "TU_CHAT_ID_AQUI"

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
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
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("Error Telegram:", e)

# ================= BINANCE SPOT =================

def get_klines():
    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df

# ================= INDICADORES =================

def add_indicators(df):
    df["ema25"] = df["close"].ewm(span=25, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema99"] = df["close"].ewm(span=99, adjust=False).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()

    df["range_high"] = df["high"].rolling(40).max()
    df["range_low"] = df["low"].rolling(40).min()

    df["ema_spread"] = (
        abs(df["ema25"] - df["ema50"]) +
        abs(df["ema50"] - df["ema99"])
    ) / df["close"]

    return df

# ================= DETECCIÓN DE MERCADO =================

def detect_market(df):
    last = df.iloc[-1]

    ema_flat = last["ema_spread"] < 0.004
    range_size = (last["range_high"] - last["range_low"]) / last["close"]

    is_range = ema_flat and range_size < 0.025

    bullish_trend = (
        last["ema25"] > last["ema50"] > last["ema99"]
        and last["close"] > last["ema25"]
    )

    bearish_trend = (
        last["ema25"] < last["ema50"] < last["ema99"]
        and last["close"] < last["ema25"]
    )

    if is_range:
        return "RANGO"

    if bullish_trend:
        return "TENDENCIA_ALCISTA"

    if bearish_trend:
        return "TENDENCIA_BAJISTA"

    return "NEUTRAL"

# ================= FILTRO DE RUPTURA =================

def breakout_filter(df):
    last = df.iloc[-1]

    high = last["range_high"]
    low = last["range_low"]

    strong_volume = last["volume"] > last["vol_ma"] * 2

    breaks_up = last["close"] > high
    breaks_down = last["close"] < low

    return strong_volume and (breaks_up or breaks_down)

# ================= FILTRO ANTI-FOMO =================

def anti_fomo_filter(df, signal):
    side, entry, tp, sl, strategy = signal
    last_price = df.iloc[-1]["close"]

    distance = abs(last_price - entry) / entry

    return distance <= MAX_DISTANCE_FROM_SIGNAL

# ================= SEÑALES DE TENDENCIA =================

def trend_signal(df, market):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    volume_ok = last["volume"] > last["vol_ma"]

    if market == "TENDENCIA_ALCISTA":
        pullback = prev["close"] < prev["ema25"] and last["close"] > last["ema25"]

        if pullback and volume_ok:
            entry = last["close"]
            tp = entry * (1 + TP_TREND)
            sl = entry * (1 - SL_TREND)
            return "COMPRA / LONG", entry, tp, sl, "Tendencia EMA + Volumen"

    if market == "TENDENCIA_BAJISTA":
        pullback = prev["close"] > prev["ema25"] and last["close"] < last["ema25"]

        if pullback and volume_ok:
            entry = last["close"]
            tp = entry * (1 - TP_TREND)
            sl = entry * (1 + SL_TREND)
            return "VENTA / SHORT", entry, tp, sl, "Tendencia EMA + Volumen"

    return None

# ================= SEÑALES DE RANGO =================

def range_signal(df):
    last = df.iloc[-1]

    price = last["close"]
    high = last["range_high"]
    low = last["range_low"]

    range_width = high - low
    zone_margin = range_width * 0.18

    near_support = price <= low + zone_margin
    near_resistance = price >= high - zone_margin

    candle_reject_support = (
        last["low"] < low + zone_margin
        and last["close"] > last["open"]
    )

    candle_reject_resistance = (
        last["high"] > high - zone_margin
        and last["close"] < last["open"]
    )

    volume_not_extreme = last["volume"] < last["vol_ma"] * 2.2

    if near_support and candle_reject_support and volume_not_extreme:
        entry = price
        tp = entry * (1 + TP_RANGE)
        sl = entry * (1 - SL_RANGE)
        return "COMPRA / LONG", entry, tp, sl, "Scalping por zona de soporte"

    if near_resistance and candle_reject_resistance and volume_not_extreme:
        entry = price
        tp = entry * (1 - TP_RANGE)
        sl = entry * (1 + SL_RANGE)
        return "VENTA / SHORT", entry, tp, sl, "Scalping por zona de resistencia"

    return None

# ================= MENSAJE =================

def format_signal(signal, market):
    side, entry, tp, sl, strategy = signal
    emoji = "🟢" if "COMPRA" in side else "🔴"

    return f"""
📊 <b>SEÑAL {SYMBOL}</b>

Tipo: {emoji} <b>{side}</b>
Entrada: <b>{entry:.2f}</b>
TP: <b>{tp:.2f}</b>
SL: <b>{sl:.2f}</b>

⏱ Temporalidad: <b>{INTERVAL}</b>
📌 Mercado: <b>{market}</b>
📈 Estrategia: <b>{strategy}</b>

🛡 Anti-FOMO: activo
🌐 Fuente: Binance Spot
⚠️ No perseguir el precio si ya se alejó de la entrada.
"""

# ================= LOOP PRINCIPAL =================

def run_bot():
    global last_signal

    send_telegram(
        f"🚀 BOT BTC SCALPING activo\n"
        f"Par: {SYMBOL}\n"
        f"Temporalidad: {INTERVAL}\n"
        f"Modo: Tendencia + Scalping por zonas + Anti-FOMO\n"
        f"Fuente: Binance Spot"
    )

    while True:
        try:
            df = get_klines()
            df = add_indicators(df)

            market = detect_market(df)
            signal = None

            if breakout_filter(df):
                print(datetime.now(), "Ruptura fuerte detectada. No operar.")
                time.sleep(SLEEP_TIME)
                continue

            if market == "RANGO":
                signal = range_signal(df)

            elif market in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
                signal = trend_signal(df, market)

            if signal:
                side, entry, tp, sl, strategy = signal

                if not anti_fomo_filter(df, signal):
                    print(datetime.now(), "Señal cancelada por anti-FOMO")
                    time.sleep(SLEEP_TIME)
                    continue

                signal_id = f"{side}-{round(entry, 0)}-{strategy}"

                if signal_id != last_signal:
                    message = format_signal(signal, market)
                    send_telegram(message)
                    print(message)
                    last_signal = signal_id

            else:
                print(datetime.now(), "Sin señal | Mercado:", market)

        except Exception as e:
            error_msg = f"⚠️ Error del bot:\n{e}"
            print(error_msg)
            send_telegram(error_msg)

        time.sleep(SLEEP_TIME)

# ================= INICIO =================

if __name__ == "__main__":
    run_bot()
