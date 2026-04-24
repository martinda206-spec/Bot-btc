import requests
import pandas as pd
import time

# 🔐 TU TOKEN DE TELEGRAM
TOKEN = "8581404343:AAHCAZh6f0V55MBRtH1knrlR-1z23sDIWM0"
CHAT_ID = "2123346158"  # tu user id

# 📊 Obtener datos de Binance
def obtener_datos():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbav","tbqav","ignore"
    ])

    df["close"] = df["close"].astype(float)
    return df

# 📈 Analizar tendencia PRO
def analizar(df):
    df["ema25"] = df["close"].ewm(span=25).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema99"] = df["close"].ewm(span=99).mean()

    ultimo = df.iloc[-1]

    precio = ultimo["close"]
    ema25 = ultimo["ema25"]
    ema50 = ultimo["ema50"]
    ema99 = ultimo["ema99"]

    # 🔥 Lógica PRO
    if ema25 > ema50 > ema99:
        return "🟢 COMPRA FUERTE", precio
    elif ema25 < ema50 < ema99:
        return "🔴 VENTA FUERTE", precio
    else:
        return "⚪ ESPERAR", precio

# 📲 Enviar mensaje a Telegram
def enviar_mensaje(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })

# 🔁 Loop infinito (24/7)
def run_bot():
    ultima_senal = None

    while True:
        try:
            df = obtener_datos()
            senal, precio = analizar(df)

            print(f"Precio: {precio} | Señal: {senal}")

            # Solo avisa si cambia la señal
            if senal != ultima_senal:
                mensaje = f"""
🚨 ALERTA BTC

Precio: {precio}

Señal: {senal}

⏰ Timeframe: 15m
                """
                enviar_mensaje(mensaje)
                ultima_senal = senal

        except Exception as e:
            print("Error:", e)

        time.sleep(60)  # cada 1 minuto

# 🚀 INICIO
run_bot()
