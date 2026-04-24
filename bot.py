import os
import time
import requests
import pandas as pd

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "2123346158")

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
LIMIT = 250

ultima_senal = None


def enviar_mensaje(texto):
    if not TOKEN:
        print("ERROR: falta TOKEN")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(
        url,
        data={"chat_id": CHAT_ID, "text": texto},
        timeout=10
    )


def obtener_datos():
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT
    }

    data = requests.get(url, params=params, timeout=10).json()

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def calcular_indicadores(df):
    # EMAs
    df["ema25"] = df["close"].ewm(span=25).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema99"] = df["close"].ewm(span=99).mean()

    # Volumen
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    # RSI 14
    delta = df["close"].diff()
    ganancia = delta.where(delta > 0, 0)
    perdida = -delta.where(delta < 0, 0)

    media_ganancia = ganancia.rolling(14).mean()
    media_perdida = perdida.rolling(14).mean()

    rs = media_ganancia / media_perdida
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()

    # ATR 14
    df["h_l"] = df["high"] - df["low"]
    df["h_pc"] = abs(df["high"] - df["close"].shift(1))
    df["l_pc"] = abs(df["low"] - df["close"].shift(1))

    df["tr"] = df[["h_l", "h_pc", "l_pc"]].max(axis=1)
    df["atr"] = df["tr"].rolling(14).mean()

    # Breakout
    df["max_20"] = df["high"].rolling(20).max()
    df["min_20"] = df["low"].rolling(20).min()

    return df


def analizar(df):
    df = calcular_indicadores(df)

    ultimo = df.iloc[-1]
    anterior = df.iloc[-2]

    precio = ultimo["close"]
    ema25 = ultimo["ema25"]
    ema50 = ultimo["ema50"]
    ema99 = ultimo["ema99"]

    volumen = ultimo["volume"]
    vol_ma20 = ultimo["vol_ma20"]

    rsi = ultimo["rsi"]
    macd = ultimo["macd"]
    macd_signal = ultimo["macd_signal"]

    atr = ultimo["atr"]

    max_20_anterior = anterior["max_20"]
    min_20_anterior = anterior["min_20"]

    if pd.isna(vol_ma20) or pd.isna(rsi) or pd.isna(atr):
        return "ESPERAR", precio, "Faltan datos suficientes", None, None

    volumen_ok = volumen > vol_ma20 * 1.20

    tendencia_alcista = precio > ema25 > ema50 > ema99
    tendencia_bajista = precio < ema25 < ema50 < ema99

    momentum_alcista = rsi > 55 and macd > macd_signal
    momentum_bajista = rsi < 45 and macd < macd_signal

    breakout_alcista = precio > max_20_anterior and volumen_ok
    breakout_bajista = precio < min_20_anterior and volumen_ok

    # LONG PRO
    if tendencia_alcista and momentum_alcista and breakout_alcista:
        stop_loss = precio - (atr * 1.5)
        take_profit = precio + (atr * 3)

        motivo = "Tendencia alcista + RSI/MACD alcista + breakout con volumen"
        return "LONG", precio, motivo, stop_loss, take_profit

    # SHORT PRO
    if tendencia_bajista and momentum_bajista and breakout_bajista:
        stop_loss = precio + (atr * 1.5)
        take_profit = precio - (atr * 3)

        motivo = "Tendencia bajista + RSI/MACD bajista + breakout con volumen"
        return "SHORT", precio, motivo, stop_loss, take_profit

    return "ESPERAR", precio, "Sin oportunidad clara", None, None


def run_bot():
    global ultima_senal

    print("Bot BTC PRO iniciado")
    enviar_mensaje("✅ Bot BTC PRO iniciado en Railway")

    while True:
        try:
            df = obtener_datos()
            senal, precio, motivo, stop_loss, take_profit = analizar(df)

            print("------")
            print("Precio:", precio)
            print("Señal:", senal)
            print("Motivo:", motivo)

            if senal != "ESPERAR" and senal != ultima_senal:
                mensaje = f"""
🚨 BTCUSDT ALERTA PRO

Señal: {senal}
Precio: {precio:.2f}
Timeframe: {INTERVAL}

Ventaja clara: SÍ
Motivo: {motivo}

🛑 Stop Loss sugerido: {stop_loss:.2f}
🎯 Take Profit sugerido: {take_profit:.2f}
"""

                enviar_mensaje(mensaje)
                ultima_senal = senal

            time.sleep(60)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


run_bot()
