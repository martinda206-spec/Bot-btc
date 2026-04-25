import os
import time
import requests
import pandas as pd

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "2123346158")

SYMBOL = "BTCUSDT"
INTERVAL = "15m"

balance = 1000.0
balance_inicial = 1000.0

apalancamiento = 5
riesgo_por_trade = 0.01

posicion_abierta = None


def enviar_mensaje(texto):
    if not TOKEN:
        print("ERROR: falta TOKEN")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": texto}, timeout=10)


def obtener_datos():
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": SYMBOL, "interval": INTERVAL, "limit": 250}

    response = requests.get(url, params=params, timeout=10)
    if response.status_code != 200:
        return None

    data = response.json()
    if not isinstance(data, list):
        return None

    df = pd.DataFrame(data)
    if df.empty:
        return None

    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]

    for col in df.columns[1:]:
        df[col] = df[col].astype(float)

    return df


def indicadores(df):
    df["ema25"] = df["close"].ewm(span=25).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema99"] = df["close"].ewm(span=99).mean()

    df["vol_ma20"] = df["volume"].rolling(20).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()

    df["max_20"] = df["high"].rolling(20).max()
    df["min_20"] = df["low"].rolling(20).min()

    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()

    return df


def detectar(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last["atr"]) or pd.isna(prev["max_20"]):
        return "ESPERAR", last["close"], None

    precio = last["close"]
    volumen_ok = last["volume"] > last["vol_ma20"] * 1.2

    long = (
        precio > last["ema25"] > last["ema50"] > last["ema99"]
        and last["rsi"] > 55
        and last["macd"] > last["macd_signal"]
        and precio > prev["max_20"]
        and volumen_ok
    )

    short = (
        precio < last["ema25"] < last["ema50"] < last["ema99"]
        and last["rsi"] < 45
        and last["macd"] < last["macd_signal"]
        and precio < prev["min_20"]
        and volumen_ok
    )

    if long:
        return "LONG", precio, last["atr"]
    if short:
        return "SHORT", precio, last["atr"]

    return "ESPERAR", precio, None


def abrir_posicion(tipo, precio, atr):
    global posicion_abierta, balance

    riesgo = balance * riesgo_por_trade
    distancia = atr * 1.5

    cantidad = riesgo / distancia
    tamaño = cantidad * precio
    margen = tamaño / apalancamiento

    if tipo == "LONG":
        sl = precio - distancia
        tp1 = precio + distancia * 2
        tp2 = precio + distancia * 3
    else:
        sl = precio + distancia
        tp1 = precio - distancia * 2
        tp2 = precio - distancia * 3

    posicion_abierta = {
        "tipo": tipo,
        "entrada": precio,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "cantidad_total": cantidad,
        "cantidad_restante": cantidad,
        "tp1_tomado": False,
        "mejor_precio": precio
    }

    enviar_mensaje(f"""
📥 NUEVA OPERACIÓN

Tipo: {tipo}
Entrada: {precio:.2f}
SL: {sl:.2f}
TP1: {tp1:.2f}
TP2: {tp2:.2f}

Balance: {balance:.2f}
""")


def gestionar(precio, atr):
    global posicion_abierta, balance

    if not posicion_abierta:
        return

    p = posicion_abierta
    entrada = p["entrada"]

    if p["tipo"] == "LONG":
        p["mejor_precio"] = max(p["mejor_precio"], precio)

        if not p["tp1_tomado"] and precio >= p["tp1"]:
            pnl = (p["tp1"] - entrada) * (p["cantidad_total"] / 2)
            balance += pnl
            p["cantidad_restante"] /= 2
            p["tp1_tomado"] = True
            p["sl"] = entrada

        if precio <= p["sl"]:
            pnl = (p["sl"] - entrada) * p["cantidad_restante"]
            balance += pnl
            cerrar()

        if precio >= p["tp2"]:
            pnl = (p["tp2"] - entrada) * p["cantidad_restante"]
            balance += pnl
            cerrar()

    else:
        p["mejor_precio"] = min(p["mejor_precio"], precio)

        if not p["tp1_tomado"] and precio <= p["tp1"]:
            pnl = (entrada - p["tp1"]) * (p["cantidad_total"] / 2)
            balance += pnl
            p["cantidad_restante"] /= 2
            p["tp1_tomado"] = True
            p["sl"] = entrada

        if precio >= p["sl"]:
            pnl = (entrada - p["sl"]) * p["cantidad_restante"]
            balance += pnl
            cerrar()

        if precio <= p["tp2"]:
            pnl = (entrada - p["tp2"]) * p["cantidad_restante"]
            balance += pnl
            cerrar()


def cerrar():
    global posicion_abierta, balance
    rendimiento = ((balance - balance_inicial) / balance_inicial) * 100

    enviar_mensaje(f"""
📤 CIERRE

Balance: {balance:.2f}
Rendimiento: {rendimiento:.2f}%
""")

    posicion_abierta = None


def run():
    enviar_mensaje("🚀 BOT PRO ACTIVO")

    while True:
        df = obtener_datos()
        if df is None:
            time.sleep(60)
            continue

        df = indicadores(df)
        señal, precio, atr = detectar(df)

        gestionar(precio, atr)

        if señal != "ESPERAR" and posicion_abierta is None:
            abrir_posicion(señal, precio, atr)

        print(balance)
        time.sleep(60)


run()
