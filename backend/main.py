from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd, numpy as np, time, threading, requests, logging
from datetime import datetime

# -------------------------------
# Configuration (تعديل هنا بسهولة)
BOT_TOKEN = "<YOUR_BOT_TOKEN>"
CHAT_ID = "<YOUR_CHAT_ID>"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
SEND_TELEGRAM = False  # فعّل عند وضع التوكن و chat id
# -------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = FastAPI(title="Crypto Signal Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for candles per symbol
STORE = {}
LOCK = threading.Lock()

class PricePayload(BaseModel):
    symbol: str
    close: float
    timestamp: int = None
    raw: dict = None

# --- Indicator implementations ---
def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=(period-1), adjust=False).mean()
    ma_down = down.ewm(com=(period-1), adjust=False).mean()
    rs = ma_up / (ma_down + 1e-12)
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def bollinger(series, window=20, stds=2):
    mid = series.rolling(window=window, min_periods=1).mean()
    std = series.rolling(window=window, min_periods=1).std()
    upper = mid + stds * std
    lower = mid - stds * std
    return lower, mid, upper

# --- Business rules for signals ---
def generate_signals(df):
    if df is None or len(df) < 3:
        return {"signal":"WAIT", "reasons":["insufficient data"]}
    close = df['close']

    try:
        rsi_v = float(rsi(close).iloc[-1])
    except Exception:
        rsi_v = None
    try:
        macd_line, macd_signal, _ = macd(close)
        macd_v = float(macd_line.iloc[-1])
        macd_sig_v = float(macd_signal.iloc[-1])
    except Exception:
        macd_v = macd_sig_v = None
    try:
        lower, mid, upper = bollinger(close)
        lower_v = float(lower.iloc[-1])
        upper_v = float(upper.iloc[-1])
    except Exception:
        lower_v = upper_v = None
    try:
        ema_v = float(ema(close, span=20).iloc[-1])
    except Exception:
        ema_v = None

    price = float(close.iloc[-1])
    reasons = []

    # RSI rules
    if rsi_v is not None:
        if rsi_v < 30:
            reasons.append("RSI < 30 (oversold)")
        elif rsi_v > 70:
            reasons.append("RSI > 70 (overbought)")
    # MACD rules
    if macd_v is not None and macd_sig_v is not None:
        if macd_v > macd_sig_v:
            reasons.append("MACD > Signal (bullish)")
        elif macd_v < macd_sig_v:
            reasons.append("MACD < Signal (bearish)")
    # Bollinger
    if lower_v is not None and upper_v is not None:
        if price < lower_v:
            reasons.append("price < Bollinger Lower")
        elif price > upper_v:
            reasons.append("price > Bollinger Upper")
    # EMA
    if ema_v is not None:
        if price > ema_v:
            reasons.append("price > EMA(20)")
        elif price < ema_v:
            reasons.append("price < EMA(20)")

    # Decide overall signal (simple aggregator)
    score = 0
    for r in reasons:
        if any(x in r.lower() for x in ['oversold','bullish','price < bollinger lower','price > ema']):
            # treat oversold, bullish, price below lower as buy
            if 'bearish' in r.lower() or 'price > bollinger upper' in r.lower() or 'overbought' in r.lower() or 'price < ema' in r.lower():
                score -= 1
            else:
                score += 1
    signal = "WAIT"
    if score >= 1:
        signal = "BUY"
    elif score <= -1:
        signal = "SELL"

    details = {
        "rsi": rsi_v,
        "macd": macd_v,
        "macd_signal": macd_sig_v,
        "boll_lower": lower_v,
        "boll_upper": upper_v,
        "ema20": ema_v,
        "price": price
    }
    return {"signal": signal, "reasons": reasons, "details": details}

# --- Telegram notifier ---
def send_telegram(symbol, price, signal, reasons):
    if not SEND_TELEGRAM:
        logging.debug("Telegram disabled; skipping send")
        return {"ok": False, "reason":"disabled"}
    text = f"{symbol} | {signal}\\nprice: {price}\\nreasons: {', '.join(reasons)}\\ntime: {datetime.utcnow().isoformat()}Z"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(TELEGRAM_API, data=payload, timeout=10)
        r.raise_for_status()
        return {"ok": True, "resp": r.json()}
    except Exception as e:
        logging.exception("Telegram send failed")
        return {"ok": False, "reason": str(e)}

# --- API endpoints ---
@app.post("/api/price")
async def receive_price(p: PricePayload):
    symbol = p.symbol.upper()
    with LOCK:
        if symbol not in STORE:
            STORE[symbol] = {"closes": []}
        store = STORE[symbol]
        store['closes'].append(float(p.close))
        # keep last 500 candles to bound memory
        if len(store['closes']) > 500:
            store['closes'] = store['closes'][-500:]
        df = pd.DataFrame({'close': store['closes']})

    # if not enough data, return wait
    if len(df) < 5:
        return {"signal":"WAIT","reasons":["not enough candles"], "details": {"count": len(df)}}

    analysis = generate_signals(df)
    # Only send Telegram when signal changes or is BUY/SELL
    last = store.get('last_signal')
    if analysis['signal'] != last:
        store['last_signal'] = analysis['signal']
        # send telegram (non-blocking suggestion: run in thread)
        try:
            threading.Thread(target=send_telegram, args=(symbol, analysis['details']['price'], analysis['signal'], analysis['reasons'])).start()
        except Exception:
            logging.exception("failed to spawn telegram thread")
    return {"signal": analysis['signal'], "reasons": analysis['reasons'], "details": analysis['details']}

@app.get("/api/status")
async def status():
    return {"status":"ok", "symbols_count": len(STORE), "time": int(time.time())}
