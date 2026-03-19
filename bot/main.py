import asyncio
import json
import os
import time
from threading import Lock, Thread
from typing import Any, Dict, List, Optional

import ccxt
import pandas as pd
import pandas_ta as ta
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot

from indicators import calculate_mso, calculate_normalized_macd

load_dotenv()

app = FastAPI()

MONITORED_SYMBOLS = ["ETH/USDT", "BTC/USDT"]
SUPPORTED_ALERT_SYMBOLS = MONITORED_SYMBOLS.copy()
STRATEGY_DEFINITIONS: Dict[str, str] = {
    "ema_cross_9_18": "EMA Cross 9/18",
    "macd_cross": "MACD Cross",
    "market_structure_85_15": "Market Structure Oscillator 85/15",
}
LEGACY_STRATEGY_ALIASES = {
    "market_structure_gt_85": "market_structure_85_15",
    "market_structure_lt_15": "market_structure_85_15",
}
SUPPORTED_ALERT_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h"]
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
}
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "bot_config.json")

# Global state to pass to frontend
bot_state = {
    "status": "Oczekuje na start...",
    "last_check": None,
    "signals": [],
    "active_settings": {
        "strategy": "ema_cross_9_18",
        "strategies": ["ema_cross_9_18"],
        "symbols": ["ETH/USDT", "BTC/USDT"],
        "timeframe": "1h",
        "repeat_alerts": False,
        "strategies_active": True,
    },
    "metrics": {
        symbol: {"mso": 50, "macd": 50, "trend": "Neutralny", "price": 0}
        for symbol in MONITORED_SYMBOLS
    }
}

# Configuration
ENV_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ENV_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ENV_PORT_RAW = os.getenv("PORT", "8000").strip()
ENV_PORT = int(ENV_PORT_RAW) if ENV_PORT_RAW.isdigit() else 8000
DEFAULT_RUNTIME_CONFIG: Dict[str, Any] = {
    "active_strategies": ["ema_cross_9_18"],
    "active_symbols": SUPPORTED_ALERT_SYMBOLS.copy(),
    "timeframe": "1h",
    "repeat_alerts": False,
    "strategies_active": True,
}


class ConfigUpdateRequest(BaseModel):
    active_strategies: Optional[List[str]] = None
    active_symbols: Optional[List[str]] = None
    # Backward-compatible single strategy input.
    active_strategy: Optional[str] = None
    timeframe: Optional[str] = None
    repeat_alerts: Optional[bool] = None
    strategies_active: Optional[bool] = None


class StrategyActivityUpdateRequest(BaseModel):
    active: bool


def _normalize_strategy_id(strategy_id: str) -> Optional[str]:
    if strategy_id in STRATEGY_DEFINITIONS:
        return strategy_id
    alias = LEGACY_STRATEGY_ALIASES.get(strategy_id)
    if alias in STRATEGY_DEFINITIONS:
        return alias
    return None


def _sanitize_strategy_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []

    sanitized: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        normalized = _normalize_strategy_id(item)
        if normalized and normalized not in sanitized:
            sanitized.append(normalized)
    return sanitized


def _normalize_symbol(symbol: str) -> Optional[str]:
    if symbol in SUPPORTED_ALERT_SYMBOLS:
        return symbol

    if symbol.endswith(":USDT"):
        normalized = symbol.replace(":USDT", "")
        if normalized in SUPPORTED_ALERT_SYMBOLS:
            return normalized

    return None


def _sanitize_symbol_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []

    sanitized: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        normalized = _normalize_symbol(item)
        if normalized and normalized not in sanitized:
            sanitized.append(normalized)
    return sanitized


def _sanitize_runtime_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = DEFAULT_RUNTIME_CONFIG.copy()

    strategies = _sanitize_strategy_list(raw.get("active_strategies"))
    if not strategies:
        legacy_strategy = raw.get("active_strategy")
        if isinstance(legacy_strategy, str):
            normalized_legacy = _normalize_strategy_id(legacy_strategy)
            if normalized_legacy:
                strategies = [normalized_legacy]

    if strategies:
        sanitized["active_strategies"] = strategies

    symbols = _sanitize_symbol_list(raw.get("active_symbols"))
    if symbols:
        sanitized["active_symbols"] = symbols

    timeframe = raw.get("timeframe")
    if timeframe in SUPPORTED_ALERT_TIMEFRAMES:
        sanitized["timeframe"] = timeframe

    repeat_alerts = raw.get("repeat_alerts")
    if isinstance(repeat_alerts, bool):
        sanitized["repeat_alerts"] = repeat_alerts

    strategies_active = raw.get("strategies_active")
    if isinstance(strategies_active, bool):
        sanitized["strategies_active"] = strategies_active

    return sanitized


def _load_runtime_config() -> Dict[str, Any]:
    merged = DEFAULT_RUNTIME_CONFIG.copy()
    if not os.path.exists(CONFIG_FILE_PATH):
        return merged

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
        if isinstance(loaded, dict):
            merged.update(loaded)
    except Exception as exc:
        print(f"Failed to load config file: {exc}")

    return _sanitize_runtime_config(merged)


def _save_runtime_config(config: Dict[str, Any]) -> None:
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"Failed to save config file: {exc}")


config_lock = Lock()
runtime_config = _load_runtime_config()


def get_runtime_config_snapshot() -> Dict[str, Any]:
    with config_lock:
        snapshot = runtime_config.copy()
        snapshot["active_strategies"] = list(runtime_config["active_strategies"])
        snapshot["active_symbols"] = list(runtime_config["active_symbols"])
        return snapshot


def refresh_active_settings_state(config: Dict[str, Any]) -> None:
    active_strategies = list(config["active_strategies"])
    active_symbols = list(config["active_symbols"])
    bot_state["active_settings"] = {
        "strategy": active_strategies[0] if active_strategies else None,
        "strategies": active_strategies,
        "symbols": active_symbols,
        "timeframe": config["timeframe"],
        "repeat_alerts": config["repeat_alerts"],
        "strategies_active": config["strategies_active"],
    }


def public_runtime_config(config: Dict[str, Any]) -> Dict[str, Any]:
    active_strategies = list(config["active_strategies"])
    active_symbols = list(config["active_symbols"])
    return {
        "telegram_token": ENV_TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": ENV_TELEGRAM_CHAT_ID,
        "telegram_token_configured": bool(ENV_TELEGRAM_BOT_TOKEN),
        "telegram_chat_id_configured": bool(ENV_TELEGRAM_CHAT_ID),
        "active_strategy": active_strategies[0] if active_strategies else None,
        "active_strategies": active_strategies,
        "active_symbols": active_symbols,
        "timeframe": config["timeframe"],
        "repeat_alerts": config["repeat_alerts"],
        "strategies_active": config["strategies_active"],
        "available_strategies": [
            {"id": strategy_id, "label": strategy_label}
            for strategy_id, strategy_label in STRATEGY_DEFINITIONS.items()
        ],
        "available_symbols": SUPPORTED_ALERT_SYMBOLS,
        "available_timeframes": SUPPORTED_ALERT_TIMEFRAMES,
    }


refresh_active_settings_state(runtime_config)

# Initialize Exchange
exchange = ccxt.bybit({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'linear' # Futures
    }
})

async def send_telegram_message(message: str, telegram_token: str, telegram_chat_id: str):
    if not telegram_token or not telegram_chat_id:
        return
    try:
        # Fresh Bot instance per send avoids stale async HTTP resources.
        bot = Bot(token=telegram_token)
        async with bot:
            await bot.send_message(chat_id=telegram_chat_id, text=message)
    except Exception as exc:
        print(f"Failed to send telegram message: {exc}")

def fetch_klines(symbol: str, timeframe: str, limit: int = 100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df: pd.DataFrame):
    # Calculate EMA 9, EMA 18
    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_18'] = ta.ema(df['close'], length=18)
    
    # Calculate Custom Indicators (from oscilator.md)
    df = calculate_normalized_macd(df)
    df = calculate_mso(df)
    
    return df


def get_poll_interval_seconds(timeframe: str) -> int:
    timeframe_seconds = TIMEFRAME_SECONDS.get(timeframe, 300)
    return max(10, min(180, timeframe_seconds // 6))


def _symbol_short_name(symbol: str) -> str:
    return symbol.split("/")[0]


def _fetch_symbol(symbol: str) -> str:
    return f"{symbol}:USDT"


def format_alert_message(signal_type: str, symbol: str, strategy_id: str, timeframe: str) -> str:
    icon = "🟢" if signal_type == "LONG" else "🔴"
    symbol_name = _symbol_short_name(symbol)
    strategy_label = STRATEGY_DEFINITIONS.get(strategy_id, strategy_id)
    return f"{icon} {signal_type} - {symbol_name} - aktywna strategia: {strategy_label} ({timeframe})"


def build_status_text(active_strategies: List[str], timeframe: str, active_symbols: List[str], strategies_active: bool) -> str:
    symbol_labels = ", ".join(_symbol_short_name(symbol) for symbol in active_symbols)
    symbols_context = f" | Pary: {symbol_labels}" if symbol_labels else ""

    if not strategies_active:
        return f"Strategie wyłączone ({timeframe}){symbols_context}"

    strategy_labels = [STRATEGY_DEFINITIONS.get(strategy_id, strategy_id) for strategy_id in active_strategies]
    if strategy_labels:
        return f"Aktywne strategie: {', '.join(strategy_labels)} ({timeframe}){symbols_context}"
    return f"Brak aktywnych strategii ({timeframe}){symbols_context}"


def evaluate_active_strategy(
    strategy_id: str,
    prev: pd.Series,
    curr: pd.Series,
    repeat_alerts: bool,
) -> Optional[str]:
    ema_cross_up = prev['ema_9'] <= prev['ema_18'] and curr['ema_9'] > curr['ema_18']
    ema_cross_down = prev['ema_9'] >= prev['ema_18'] and curr['ema_9'] < curr['ema_18']

    macd_cross_up = prev['macd_raw'] <= prev['macd_signal_raw'] and curr['macd_raw'] > curr['macd_signal_raw']
    macd_cross_down = prev['macd_raw'] >= prev['macd_signal_raw'] and curr['macd_raw'] < curr['macd_signal_raw']

    if strategy_id == 'ema_cross_9_18':
        if ema_cross_up:
            return "LONG"
        if ema_cross_down:
            return "SHORT"
        return None

    if strategy_id == 'macd_cross':
        if macd_cross_up:
            return "LONG"
        if macd_cross_down:
            return "SHORT"
        return None

    if strategy_id == 'market_structure_85_15':
        is_above = curr['mso'] > 85
        crossed_above = prev['mso'] <= 85 and is_above
        if is_above and (repeat_alerts or crossed_above):
            return "SHORT"
        is_below = curr['mso'] < 15
        crossed_below = prev['mso'] >= 15 and is_below
        if is_below and (repeat_alerts or crossed_below):
            return "LONG"
        return None

    return None

def bot_loop():
    print("Starting bot loop...")
    if ENV_TELEGRAM_BOT_TOKEN and ENV_TELEGRAM_CHAT_ID:
        asyncio.run(send_telegram_message(
            "🤖 AI Crypto Trader Alert Engine started",
            ENV_TELEGRAM_BOT_TOKEN,
            ENV_TELEGRAM_CHAT_ID,
        ))

    # Prevent repeated messages for the same symbol, strategy and closed candle.
    last_alert_marker: Dict[str, int] = {}
    
    while True:
        config = get_runtime_config_snapshot()
        active_strategies = config['active_strategies']
        active_symbols = config['active_symbols']
        timeframe = config['timeframe']
        repeat_alerts = config['repeat_alerts']
        strategies_active = config['strategies_active']
        refresh_active_settings_state(config)

        try:
            for symbol in active_symbols:
                df = fetch_klines(_fetch_symbol(symbol), timeframe, 250)
                df = calculate_indicators(df)

                if len(df) < 4:
                    continue
                
                # Evaluate the last fully closed candle to avoid intrabar noise.
                curr = df.iloc[-2]
                prev = df.iloc[-3]
                closed_candle_timestamp = int(curr['timestamp'].timestamp())

                if strategies_active:
                    for strategy_id in active_strategies:
                        signal_type = evaluate_active_strategy(
                            strategy_id,
                            prev,
                            curr,
                            repeat_alerts,
                        )

                        if not signal_type:
                            continue

                        marker_key = f"{symbol}|{timeframe}|{strategy_id}|{signal_type}"
                        already_sent_for_candle = last_alert_marker.get(marker_key) == closed_candle_timestamp

                        if already_sent_for_candle:
                            continue

                        message = format_alert_message(signal_type, symbol, strategy_id, timeframe)
                        print(f"{symbol} {message}")
                        asyncio.run(send_telegram_message(
                            message,
                            ENV_TELEGRAM_BOT_TOKEN,
                            ENV_TELEGRAM_CHAT_ID,
                        ))
                        last_alert_marker[marker_key] = closed_candle_timestamp

                        bot_state["signals"].insert(0, {
                            "pair": symbol,
                            "type": signal_type,
                            "time": time.strftime("%H:%M:%S"),
                            "reason": message,
                        })

                        bot_state["signals"] = bot_state["signals"][:20]
                
                # Update frontend metrics
                mso_curr = float(curr['mso']) if pd.notna(curr['mso']) else 50.0
                macd_norm_curr = float(curr['macd_norm']) if pd.notna(curr['macd_norm']) else 50.0
                trend = "Byczy" if pd.notna(curr['ema_9']) and pd.notna(curr['ema_18']) and curr['ema_9'] >= curr['ema_18'] else "Niedźwiedzi"

                bot_state["metrics"][symbol] = {
                    "mso": round(mso_curr, 1),
                    "macd": round(macd_norm_curr, 1),
                    "trend": trend,
                    "price": round(curr['close'], 2)
                }
            
            bot_state["status"] = build_status_text(active_strategies, timeframe, active_symbols, strategies_active)
            bot_state["last_check"] = time.strftime("%H:%M:%S")
            time.sleep(get_poll_interval_seconds(timeframe))
        except Exception as e:
            print(f"Error in bot loop: {e}")
            bot_state["status"] = f"Błąd: {str(e)}"
            time.sleep(30)

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


@app.get("/api/config")
def get_config():
    config = get_runtime_config_snapshot()
    return {"status": "success", "data": public_runtime_config(config)}

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
                "macdLine": row['macd_line'] if pd.notna(row['macd_line']) else None,
                "macdSignal": row['macd_signal'] if pd.notna(row['macd_signal']) else None,
                "cycleHist": row['cycle_hist'] if pd.notna(row['cycle_hist']) else None,
            })
        return {"status": "success", "data": chart_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/config")
def update_config(data: ConfigUpdateRequest):
    with config_lock:
        next_config = runtime_config.copy()

        if data.active_strategies is not None:
            sanitized_strategies = _sanitize_strategy_list(data.active_strategies)
            if not sanitized_strategies:
                raise HTTPException(status_code=400, detail="Wybierz co najmniej jedną obsługiwaną strategię")
            next_config["active_strategies"] = sanitized_strategies
        elif data.active_strategy is not None:
            normalized_strategy = _normalize_strategy_id(data.active_strategy)
            if not normalized_strategy:
                raise HTTPException(status_code=400, detail="Nieobsługiwana strategia")
            next_config["active_strategies"] = [normalized_strategy]

        if data.active_symbols is not None:
            sanitized_symbols = _sanitize_symbol_list(data.active_symbols)
            if not sanitized_symbols:
                raise HTTPException(status_code=400, detail="Wybierz co najmniej jedną obsługiwaną parę")
            next_config["active_symbols"] = sanitized_symbols

        if data.timeframe is not None:
            if data.timeframe not in SUPPORTED_ALERT_TIMEFRAMES:
                raise HTTPException(status_code=400, detail="Nieobsługiwany timeframe")
            next_config["timeframe"] = data.timeframe

        if data.repeat_alerts is not None:
            next_config["repeat_alerts"] = data.repeat_alerts

        if data.strategies_active is not None:
            next_config["strategies_active"] = data.strategies_active

        sanitized_next = _sanitize_runtime_config(next_config)
        runtime_config.clear()
        runtime_config.update(sanitized_next)
        _save_runtime_config(runtime_config)
        snapshot = runtime_config.copy()

    refresh_active_settings_state(snapshot)
    bot_state["status"] = build_status_text(
        snapshot["active_strategies"],
        snapshot["timeframe"],
        snapshot["active_symbols"],
        snapshot["strategies_active"],
    )

    if ENV_TELEGRAM_BOT_TOKEN and ENV_TELEGRAM_CHAT_ID:
        asyncio.run(send_telegram_message(
            "✅ Konfiguracja alertów zapisana.",
            ENV_TELEGRAM_BOT_TOKEN,
            ENV_TELEGRAM_CHAT_ID,
        ))

    return {"status": "success", "data": public_runtime_config(snapshot)}


@app.post("/api/strategies/active")
def update_strategies_activity(data: StrategyActivityUpdateRequest):
    with config_lock:
        next_config = runtime_config.copy()
        next_config["strategies_active"] = data.active

        sanitized_next = _sanitize_runtime_config(next_config)
        runtime_config.clear()
        runtime_config.update(sanitized_next)
        _save_runtime_config(runtime_config)
        snapshot = runtime_config.copy()

    refresh_active_settings_state(snapshot)
    bot_state["status"] = build_status_text(
        snapshot["active_strategies"],
        snapshot["timeframe"],
        snapshot["active_symbols"],
        snapshot["strategies_active"],
    )

    return {"status": "success", "data": {"strategies_active": snapshot["strategies_active"]}}

if __name__ == "__main__":
    # Start bot loop in a background thread
    thread = Thread(target=bot_loop, daemon=True)
    thread.start()
    
    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=ENV_PORT)
