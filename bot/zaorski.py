"""
ZAORSKI strategy — contrarian sentiment analysis for BTC.

Logic: when the crowd is extremely one-sided (too many longs or too many shorts),
Zaorski goes the opposite way. Four data sources are combined into a composite score:

  Funding Rate  — extreme negative = crowd short = LONG opportunity
  Fear & Greed  — extreme fear = LONG, extreme greed = SHORT
  Long/Short    — extreme ratio = contrarian signal
  Open Interest — OI rising while price falling = squeeze setup (LONG bias)

Composite score >= +55  → LONG alert
Composite score <= -55  → SHORT alert
Otherwise               → no signal
"""

from typing import Dict, List, Optional, Tuple

import requests

ZAORSKI_SYMBOL = "BTC/USDT"
_BYBIT_SYMBOL = "BTCUSDT"


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def fetch_funding_rate(exchange) -> Optional[float]:
    """Returns current 8h funding rate as decimal (e.g. 0.0001 = 0.01%)."""
    try:
        data = exchange.fetch_funding_rate(f"{ZAORSKI_SYMBOL}:USDT")
        return float(data["fundingRate"])
    except Exception as exc:
        print(f"[ZAORSKI] funding rate: {exc}")
        return None


def fetch_fear_greed() -> Optional[Dict]:
    """Returns current Fear & Greed index value and label."""
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        resp.raise_for_status()
        item = resp.json()["data"][0]
        return {"value": int(item["value"]), "label": item["value_classification"]}
    except Exception as exc:
        print(f"[ZAORSKI] fear & greed: {exc}")
        return None


def fetch_long_short_ratio() -> Optional[float]:
    """Returns buy/sell account ratio from Bybit (>1 = more longs, <1 = more shorts)."""
    try:
        url = "https://api.bybit.com/v5/market/account-ratio"
        params = {"category": "linear", "symbol": _BYBIT_SYMBOL, "period": "1h", "limit": 1}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("result", {}).get("list", [])
        if items:
            buy = float(items[0]["buyRatio"])
            sell = float(items[0]["sellRatio"])
            if sell > 0:
                return round(buy / sell, 3)
        return None
    except Exception as exc:
        print(f"[ZAORSKI] long/short ratio: {exc}")
        return None


def fetch_open_interest_change(exchange) -> Optional[Dict]:
    """Returns current OI in USD and recent 4h price change %."""
    try:
        oi_data = exchange.fetch_open_interest(f"{ZAORSKI_SYMBOL}:USDT")
        oi_usd = float(oi_data["openInterestValue"])

        bars = exchange.fetch_ohlcv(f"{ZAORSKI_SYMBOL}:USDT", "4h", limit=3)
        price_prev = float(bars[-2][4])
        price_now = float(bars[-1][4])
        price_change_pct = round(((price_now - price_prev) / price_prev) * 100, 2)

        return {"oi_usd": oi_usd, "price_change_pct": price_change_pct}
    except Exception as exc:
        print(f"[ZAORSKI] open interest: {exc}")
        return None


# ---------------------------------------------------------------------------
# Scoring functions  (-100 = strong SHORT bias, +100 = strong LONG bias)
# ---------------------------------------------------------------------------

def _score_funding(rate: float) -> Tuple[int, str]:
    pct = rate * 100
    if pct < -0.05:
        return 100, f"{pct:.4f}% 🔥 Ekstremalne shortowanie → contrarian LONG"
    if pct < -0.02:
        return 60, f"{pct:.4f}% Funding ujemny → lekki sygnał LONG"
    if pct < 0.03:
        return 0, f"{pct:.4f}% Neutralny"
    if pct < 0.08:
        return -60, f"{pct:.4f}% Funding dodatni → lekki sygnał SHORT"
    return -100, f"{pct:.4f}% 🔥 Ekstremalne longowanie → contrarian SHORT"


def _score_fear_greed(value: int, raw_label: str) -> Tuple[int, str]:
    if value <= 20:
        return 100, f"{value} — {raw_label} 😱 → contrarian LONG"
    if value <= 35:
        return 50, f"{value} — {raw_label} → lekki sygnał LONG"
    if value <= 65:
        return 0, f"{value} — {raw_label} Neutralny"
    if value <= 80:
        return -50, f"{value} — {raw_label} → lekki sygnał SHORT"
    return -100, f"{value} — {raw_label} 🤑 → contrarian SHORT"


def _score_ls_ratio(ratio: float) -> Tuple[int, str]:
    if ratio < 0.60:
        return 100, f"{ratio:.2f} — shorts dominują 🐻 → contrarian LONG"
    if ratio < 0.85:
        return 40, f"{ratio:.2f} — lekka przewaga shortów → LONG bias"
    if ratio < 1.15:
        return 0, f"{ratio:.2f} — balans"
    if ratio < 1.40:
        return -40, f"{ratio:.2f} — lekka przewaga longów → SHORT bias"
    return -100, f"{ratio:.2f} — longi dominują 🐂 → contrarian SHORT"


def _score_oi(oi_data: Dict) -> Tuple[int, str]:
    price_chg = oi_data["price_change_pct"]
    oi_b = oi_data["oi_usd"] / 1_000_000_000
    if price_chg < -2:
        return 50, f"${oi_b:.1f}B | Cena: {price_chg:+.1f}% → shortowanie przy spadkach → squeeze ryzyko"
    if price_chg > 2:
        return -30, f"${oi_b:.1f}B | Cena: {price_chg:+.1f}% → longowanie przy wzrostach → uwaga na szczyt"
    return 0, f"${oi_b:.1f}B | Cena: {price_chg:+.1f}% → neutralny"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_zaorski_signal(exchange) -> Optional[Dict]:
    """
    Fetch all sentiment data, compute composite score, return signal dict or None.

    Return dict shape:
        { "signal": "LONG"|"SHORT", "score": int, "details": [(label, description)] }
    """
    scores: List[int] = []
    details: List[Tuple[str, str]] = []

    funding = fetch_funding_rate(exchange)
    if funding is not None:
        s, d = _score_funding(funding)
        scores.append(s)
        details.append(("Funding Rate", d))

    fg = fetch_fear_greed()
    if fg is not None:
        s, d = _score_fear_greed(fg["value"], fg["label"])
        scores.append(s)
        details.append(("Fear & Greed", d))

    ls = fetch_long_short_ratio()
    if ls is not None:
        s, d = _score_ls_ratio(ls)
        scores.append(s)
        details.append(("Long/Short Ratio", d))

    oi = fetch_open_interest_change(exchange)
    if oi is not None:
        s, d = _score_oi(oi)
        scores.append(s)
        details.append(("Open Interest", d))

    if not scores:
        return None

    composite = round(sum(scores) / len(scores))

    if composite >= 55:
        signal = "LONG"
    elif composite <= -55:
        signal = "SHORT"
    else:
        return None

    return {"signal": signal, "score": composite, "details": details}


def format_zaorski_alert(result: Dict) -> str:
    signal = result["signal"]
    score = result["score"]
    icon = "🟢" if signal == "LONG" else "🔴"

    lines = [
        f"{icon} ZAORSKI: {signal} — BTC",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for label, desc in result["details"]:
        lines.append(f"📊 {label}: {desc}")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💡 Wynik: {score:+d}/100 → {signal}")
    lines.append("(idź pod prąd tłumu)")

    return "\n".join(lines)
