import os
import time
import requests
import pandas as pd

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "2123346158")

SYMBOL = "BTCUSDT"
INTERVAL = "15m"

balance = 100.0
apalancamiento = 3
margen_por_trade = 0.30

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
        print("Error HTTP Binance:", response.status_code)
        return None

    data = response.json()

    if not isinstance(data, list):
        print("Error datos Binance:", data)
        return None

    df = pd.DataFrame(data)

    if df.empty:
        print("DataFrame vacío")
        return None

    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]

    for col in ["open", "high", "low", "close", "volume"]:
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

    precio = last["close"]

    if (
        pd.isna(last["vol_ma20"])
        or pd.isna(last["rsi"])
        or pd.isna(last["atr"])
        or pd.isna(prev["max_20"])
        or pd.isna(prev["min_20"])
    ):
        return "ESPERAR", precio, None

    volumen_ok = last["volume"] > last["vol_ma20"] * 1.2

    tendencia_long = precio > last["ema25"] > last["ema50"] > last["ema99"]
    tendencia_short = precio < last["ema25"] < last["ema50"] < last["ema99"]

    momentum_long = last["rsi"] > 55 and last["macd"] > last["macd_signal"]
    momentum_short = last["rsi"] < 45 and last["macd"] < last["macd_signal"]

    breakout_long = precio > prev["max_20"]
    breakout_short = precio < prev["min_20"]

    if tendencia_long and momentum_long and breakout_long and volumen_ok:
        return "LONG", precio, last["atr"]

    if tendencia_short and momentum_short and breakout_short and volumen_ok:
        return "SHORT", precio, last["atr"]

    return "ESPERAR", precio, None


def abrir_posicion(tipo, precio, atr):
    global posicion_abierta, balance

    if atr is None or pd.isna(atr) or atr <= 0:
        return

    margen = balance * margen_por_trade
    tamaño_posicion = margen * apalancamiento
    cantidad_btc = tamaño_posicion / precio

    if tipo == "LONG":
        sl = precio - atr * 1.5
        tp = precio + atr * 3
    else:
        sl = precio + atr * 1.5
        tp = precio - atr * 3

    posicion_abierta = {
        "tipo": tipo,
        "entrada": precio,
        "sl": sl,
        "tp": tp,
        "margen": margen,
        "tamaño": tamaño_posicion,
        "cantidad": cantidad_btc
    }

    enviar_mensaje(f"""
📥 NUEVA OPERACIÓN SIMULADA

Tipo: {tipo}
Entrada: {precio:.2f}

Apalancamiento: {apalancamiento}x
Margen usado: {margen:.2f} USDT
Tamaño posición: {tamaño_posicion:.2f} USDT

SL: {sl:.2f}
TP: {tp:.2f}

Balance actual: {balance:.2f} USDT
""")


def gestionar_posicion(precio):
    global posicion_abierta, balance

    if not posicion_abierta:
        return

    tipo = posicion_abierta["tipo"]
    entrada = posicion_abierta["entrada"]
    sl = posicion_abierta["sl"]
    tp = posicion_abierta["tp"]
    cantidad = posicion_abierta["cantidad"]

    cerrar = False
    resultado = ""
    pnl = 0.0

    if tipo == "LONG":
        if precio <= sl:
            pnl = (sl - entrada) * cantidad
            resultado = "❌ STOP LOSS"
            cerrar = True
        elif precio >= tp:
            pnl = (tp - entrada) * cantidad
            resultado = "✅ TAKE PROFIT"
            cerrar = True

    elif tipo == "SHORT":
        if precio >= sl:
            pnl = (entrada - sl) * cantidad
            resultado = "❌ STOP LOSS"
            cerrar = True
        elif precio <= tp:
            pnl = (entrada - tp) * cantidad
            resultado = "✅ TAKE PROFIT"
            cerrar = True

    if cerrar:
        balance += pnl

        enviar_mensaje(f"""
📤 CIERRE OPERACIÓN SIMULADA

Resultado: {resultado}
PnL: {pnl:.2f} USDT

Balance actualizado: {balance:.2f} USDT
""")

        posicion_abierta = None


def run():
    enviar_mensaje(f"""
🚀 Simulador iniciado

Balance inicial: {balance:.2f} USDT
Apalancamiento: {apalancamiento}x
Margen por operación: {margen_por_trade * 100:.0f}%
Timeframe: {INTERVAL}
""")

    while True:
        try:
            df = obtener_datos()

            if df is None:
                time.sleep(60)
                continue

            df = indicadores(df)

            señal, precio, atr = detectar(df)

            gestionar_posicion(precio)

            if señal != "ESPERAR" and posicion_abierta is None:
                abrir_posicion(señal, precio, atr)

            print("Precio:", precio, "Balance:", balance, "Señal:", señal)

            time.sleep(60)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


run()
