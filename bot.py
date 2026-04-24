import os
import time
import requests
import pandas as pd

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "2123346158")

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
LIMIT = 200

ultima_senal = None

def enviar_mensaje(texto):
    if not TOKEN:
        print("ERROR: falta configurar TOKEN en Railway Variables")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": texto}, timeout=10)

def obtener_datos():
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": SYMBOL, "interval": INTERVAL, "limit": LIMIT}

    data = requests.get(url, params=params, timeout=10).json()

    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]

    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df

def analizar(df):
    df["ema25"] = df["close"].ewm(span=25).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema99"] = df["close"].ewm(span=99).mean()
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    ultimo = df.iloc[-1]

    precio = ultimo["close"]
    ema25 = ultimo["ema25"]
    ema50 = ultimo["ema50"]
    ema99 = ultimo["ema99"]
    volumen = ultimo["volume"]
    vol_ma20 = ultimo["vol_ma20"]

    if pd.isna(vol_ma20):
        return "ESPERAR", precio, "Sin datos suficientes"

    volumen_ok = volumen > vol_ma20 * 1.10

    if precio > ema25 > ema50 > ema99 and volumen_ok:
        return "LONG", precio, "Tendencia alcista + volumen confirmado"

    elif precio < ema25 < ema50 < ema99 and volumen_ok:
        return "SHORT", precio, "Tendencia bajista + volumen confirmado"

    else:
        return "ESPERAR", precio, "Sin ventaja clara"

def run_bot():
    global ultima_senal

    print("Bot BTC iniciado correctamente")
    enviar_mensaje("✅ Bot BTC funcionando en Railway")

    while True:
        try:
            df = obtener_datos()
            senal, precio, motivo = analizar(df)

            print("------")
            print("Precio:", precio)
            print("Señal:", senal)
            print("Motivo:", motivo)

            if senal != "ESPERAR" and senal != ultima_senal:
                mensaje = f"""
🚨 BTC ALERTA

Señal: {senal}
Precio: {precio}
Timeframe: {INTERVAL}

Ventaja clara: SÍ
Motivo: {motivo}
"""
                enviar_mensaje(mensaje)
                ultima_senal = senal

            time.sleep(60)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)

run_bot()
