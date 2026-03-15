import ccxt
import pandas as pd
import pandas_ta as ta
import time
import os
from dotenv import load_dotenv
import asyncio
from telegram import Bot
from fastapi import FastAPI
import uvicorn
from threading import Thread
from pydantic import BaseModel
from typing import List, Dict, Any

load_dotenv()

app = FastAPI()

# Global state to pass to frontend
bot_state = {
    "status": "Oczekuje na start...",
    "last_check": None,
    "signals": [],
    "metrics": {
        "ETH/USDT": {"mso": 50, "macd": 50, "trend": "Neutralny", "price": 0},
        "BTC/USDT": {"mso": 50, "macd": 50, "trend": "Neutralny", "price": 0}
    }
}

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Initialize Exchange
exchange = ccxt.bybit({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'linear' # Futures
    }
})

# Initialize Telegram Bot
if TELEGRAM_BOT_TOKEN:
    telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)
else:
    telegram_bot = None

async def send_telegram_message(message: str):
    if telegram_bot and TELEGRAM_CHAT_ID:
        try:
            await telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        except Exception as e:
            print(f"Failed to send telegram message: {e}")

def fetch_klines(symbol: str, timeframe: str, limit: int = 100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

from indicators import calculate_normalized_macd, calculate_mso

def calculate_indicators(df: pd.DataFrame):
    # Calculate EMA 9, EMA 18
    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_18'] = ta.ema(df['close'], length=18)
    
    # Calculate Custom Indicators (from oscilator.md)
    df = calculate_normalized_macd(df)
    df = calculate_mso(df)
    
    return df

def bot_loop():
    print("Starting bot loop...")
    asyncio.run(send_telegram_message("🤖 Antigravity Crypto Bot Started: Monitoring ETH & BTC"))
    
    # Keep track of last signals to prevent spamming
    last_signal = {'ETH/USDT:USDT': None, 'BTC/USDT:USDT': None}
    
    while True:
        try:
            for symbol in ['ETH/USDT:USDT', 'BTC/USDT:USDT']:
                df = fetch_klines(symbol, '1h', 250)
                df = calculate_indicators(df)
                
                # Get latest values (last closed bar or current open bar)
                # It's usually safer to check the last closed bar index [-2] or current [-1]
                curr = df.iloc[-1]
                prev = df.iloc[-2]
                
                # State Variables
                macd_norm_curr = curr['macd_norm']
                mso_curr = curr['mso']
                
                # EMA crosses
                ema_cross_up = prev['ema_9'] <= prev['ema_18'] and curr['ema_9'] > curr['ema_18']
                ema_cross_down = prev['ema_9'] >= prev['ema_18'] and curr['ema_9'] < curr['ema_18']
                
                # MACD crosses
                macd_cross_up = prev['macd_raw'] <= prev['macd_signal_raw'] and curr['macd_raw'] > curr['macd_signal_raw']
                macd_cross_down = prev['macd_raw'] >= prev['macd_signal_raw'] and curr['macd_raw'] < curr['macd_signal_raw']
                
                signal = None
                
                # --- [STRATEGIA 1] ---
                # Przecięcie EMA 9 i EMA 18
                # Jeśli MACD < 50 => CALL LONG
                # Jeśli MACD > 50 => CALL SHORT
                if ema_cross_up and macd_norm_curr < 50:
                    signal = f"🟢 [STRATEGIA 1] {symbol} CALL LONG (Cross EMA, MACD < 50)"
                elif ema_cross_down and macd_norm_curr > 50:
                    signal = f"🔴 [STRATEGIA 1] {symbol} CALL SHORT (Cross EMA, MACD > 50)"
                
                # --- [STRATEGIA 2] ---
                # Jeśli oscylator miedzy 80 a 100 i cross spadkowy na macd - call sell
                # Jeśli miedzy 0 a 20 i cross wzrostowy na macd - call long
                if 80 <= mso_curr <= 100 and macd_cross_down:
                    signal = f"🔴 [STRATEGIA 2] {symbol} CALL SHORT (MSO: {mso_curr:.1f}, MACD Cross Down)"
                elif 0 <= mso_curr <= 20 and macd_cross_up:
                    signal = f"🟢 [STRATEGIA 2] {symbol} CALL LONG (MSO: {mso_curr:.1f}, MACD Cross Up)"
                
                if signal and signal != last_signal[symbol]:
                    print(signal)
                    asyncio.run(send_telegram_message(signal))
                    last_signal[symbol] = signal
                    
                    # Add to frontend state
                    bot_state["signals"].insert(0, {
                        "pair": symbol.replace(':USDT', ''),
                        "type": "LONG" if "LONG" in signal else "SHORT" if "SHORT" in signal else "INFO",
                        "time": time.strftime("%H:%M:%S"),
                        "reason": signal.split("] ")[1] if "] " in signal else signal
                    })
                    
                    # Keep only last 10 signals
                    bot_state["signals"] = bot_state["signals"][:10]
                
                # Update frontend metrics
                bot_state["metrics"][symbol.replace(':USDT', '')] = {
                    "mso": round(mso_curr, 1),
                    "macd": round(macd_norm_curr, 1),
                    "trend": "Byczy" if ema_cross_up or (prev['ema_9'] > prev['ema_18']) else "Niedźwiedzi",
                    "price": round(curr['close'], 2)
                }
            
            bot_state["status"] = "Aktywnie monitoruje rynek"
            bot_state["last_check"] = time.strftime("%H:%M:%S")
            time.sleep(300) # Sprawdzaj co 5 minut (300 sekund)
        except Exception as e:
            print(f"Error in bot loop: {e}")
            bot_state["status"] = f"Błąd: {str(e)}"
            time.sleep(60)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/state")
def get_state():
    return bot_state

@app.get("/api/chart")
def get_chart(symbol: str = "ETH/USDT", timeframe: str = "1h"):
    try:
        # ccxt needs 'ETH/USDT:USDT' format for linear futures
        fetch_symbol = f"{symbol}:USDT"
        
        # Download more candles initially to have enough for EMA calculation properly
        df = fetch_klines(fetch_symbol, timeframe, limit=200)
        df = calculate_indicators(df)
        
        chart_data = []
        # Return last 100 candles to frontend to preserve fast rendering
        for _, row in df.tail(100).iterrows():
            chart_data.append({
                "time": int(row['timestamp'].timestamp()),
                "open": row['open'],
                "high": row['high'],
                "low": row['low'],
                "close": row['close'],
                "ema9": row['ema_9'] if pd.notna(row['ema_9']) else None,
                "ema18": row['ema_18'] if pd.notna(row['ema_18']) else None,
                "mso": row['mso'] if pd.notna(row['mso']) else None,
            })
        return {"status": "success", "data": chart_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/config")
def update_config(data: dict):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, telegram_bot
    TELEGRAM_BOT_TOKEN = data.get("telegram_token", TELEGRAM_BOT_TOKEN)
    TELEGRAM_CHAT_ID = data.get("telegram_chat_id", TELEGRAM_CHAT_ID)
    
    if TELEGRAM_BOT_TOKEN:
        telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)
        asyncio.run(send_telegram_message("✅ Konfiguracja Telegram zapisana. Otrzymujesz powiadomienia!"))
        
    return {"status": "success"}

if __name__ == "__main__":
    # Start bot loop in a background thread
    thread = Thread(target=bot_loop, daemon=True)
    thread.start()
    
    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8000)
