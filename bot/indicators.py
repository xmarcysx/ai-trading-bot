import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from collections import deque
from typing import Deque


@dataclass
class SwingState:
    last_price: float = np.nan
    mid_price: float = np.nan
    prev_price: float = np.nan
    last_index: int = -1
    mid_index: int = -1
    prev_index: int = -1
    is_crossed: bool = False


@dataclass
class NormalizeState:
    os_state: int = 0
    max_price: float = np.nan
    min_price: float = np.nan
    smooth_values: Deque[float] = field(default_factory=deque)


def _query_patterns(last_price: float, mid_price: float, prev_price: float, is_swing_high: bool) -> bool:
    if np.isnan(last_price) or np.isnan(mid_price) or np.isnan(prev_price):
        return False
    if is_swing_high:
        return prev_price < mid_price and mid_price >= last_price
    return prev_price > mid_price and mid_price <= last_price


def _update_pattern(state: SwingState, price: float, index: int) -> None:
    state.is_crossed = False
    state.prev_price = state.mid_price
    state.mid_price = state.last_price
    state.last_price = price
    state.prev_index = state.mid_index
    state.mid_index = state.last_index
    state.last_index = index


def _normalize_step(close_price: float, buy: bool, sell: bool, state: NormalizeState, smooth: int) -> float:
    previous_os = state.os_state
    if buy:
        state.os_state = 1
    elif sell:
        state.os_state = -1

    if state.os_state > previous_os:
        state.max_price = close_price
    elif state.os_state == previous_os:
        if np.isnan(state.max_price):
            state.max_price = close_price
        else:
            state.max_price = max(close_price, state.max_price)

    if state.os_state < previous_os:
        state.min_price = close_price
    elif state.os_state == previous_os:
        if np.isnan(state.min_price):
            state.min_price = close_price
        else:
            state.min_price = min(close_price, state.min_price)

    if np.isnan(state.max_price) or np.isnan(state.min_price) or state.max_price == state.min_price:
        normalized = 50.0
    else:
        normalized = (close_price - state.min_price) / (state.max_price - state.min_price) * 100.0

    state.smooth_values.append(normalized)
    if len(state.smooth_values) > smooth:
        state.smooth_values.popleft()

    return float(np.mean(state.smooth_values))

def _normalize_to_100(series: pd.Series, lookback: int) -> pd.Series:
    lowest = series.rolling(window=lookback, min_periods=1).min()
    highest = series.rolling(window=lookback, min_periods=1).max()
    denominator = (highest - lowest).replace(0, np.nan)
    normalized = ((series - lowest) / denominator) * 100.0
    return normalized.fillna(50.0)

def calculate_normalized_macd(df: pd.DataFrame, fast=12, slow=26, signal=9, norm_len=200, norm_smooth=3):
    # Calculate raw MACD components.
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_raw = ema_fast - ema_slow
    signal_raw = macd_raw.ewm(span=signal, adjust=False).mean()
    hist_raw = macd_raw - signal_raw
    
    # Keep chart values in a shared 0-100 space for an oscillator pane.
    macd_norm = _normalize_to_100(macd_raw, norm_len).rolling(window=norm_smooth, min_periods=1).mean()
    signal_norm = _normalize_to_100(signal_raw, norm_len).rolling(window=norm_smooth, min_periods=1).mean()
    hist_norm = _normalize_to_100(hist_raw, norm_len).rolling(window=norm_smooth, min_periods=1).mean()

    # Existing bot logic reads macd_norm + raw cross values.
    df['macd_norm'] = macd_norm
    df['macd_raw'] = macd_raw
    df['macd_signal_raw'] = signal_raw

    # Frontend oscillator pane series.
    df['macd_line'] = macd_norm
    df['macd_signal'] = signal_norm
    df['macd_hist'] = hist_norm
    df['macd_hist_raw'] = hist_raw
    
    return df

def calculate_mso(
    df: pd.DataFrame,
    norm_smooth: int = 4,
    cyc_smooth: int = 7,
    weight_k1: float = 1.0,
    weight_k2: float = 3.0,
    weight_k3: float = 2.0,
):
    """Approximate LuxAlgo Market Structure Oscillator with cycle histogram output."""
    closes = df['close'].to_numpy(dtype=float)
    highs = df['high'].to_numpy(dtype=float)
    lows = df['low'].to_numpy(dtype=float)

    st_high = SwingState()
    st_low = SwingState()
    it_high = SwingState()
    it_low = SwingState()
    lt_high = SwingState()
    lt_low = SwingState()

    st_norm = NormalizeState()
    it_norm = NormalizeState()
    lt_norm = NormalizeState()

    prev_it_swing_high = False
    prev_it_swing_low = False
    prev_lt_swing_high = False
    prev_lt_swing_low = False

    st_values = []
    it_values = []
    lt_values = []
    mso_values = []

    for i in range(len(df)):
        close_value = closes[i]
        bull_st = False
        bear_st = False

        if i >= 2 and _query_patterns(highs[i], highs[i - 1], highs[i - 2], True):
            _update_pattern(st_high, highs[i - 1], i - 1)

        if not np.isnan(st_high.last_price) and close_value > st_high.last_price and not st_high.is_crossed:
            st_high.is_crossed = True
            bull_st = True

        if i >= 2 and _query_patterns(lows[i], lows[i - 1], lows[i - 2], False):
            _update_pattern(st_low, lows[i - 1], i - 1)

        if not np.isnan(st_low.last_price) and close_value < st_low.last_price and not st_low.is_crossed:
            st_low.is_crossed = True
            bear_st = True

        st_value = _normalize_step(close_value, bull_st, bear_st, st_norm, norm_smooth)

        bull_it = False
        bear_it = False

        c_swing_high_it = _query_patterns(st_high.last_price, st_high.mid_price, st_high.prev_price, True)
        if c_swing_high_it and c_swing_high_it != prev_it_swing_high and not np.isnan(st_high.mid_price) and st_high.mid_index >= 0:
            _update_pattern(it_high, st_high.mid_price, st_high.mid_index)

        if not np.isnan(it_high.last_price) and close_value > it_high.last_price and not it_high.is_crossed:
            it_high.is_crossed = True
            bull_it = True

        c_swing_low_it = _query_patterns(st_low.last_price, st_low.mid_price, st_low.prev_price, False)
        if c_swing_low_it and c_swing_low_it != prev_it_swing_low and not np.isnan(st_low.mid_price) and st_low.mid_index >= 0:
            _update_pattern(it_low, st_low.mid_price, st_low.mid_index)

        if not np.isnan(it_low.last_price) and close_value < it_low.last_price and not it_low.is_crossed:
            it_low.is_crossed = True
            bear_it = True

        prev_it_swing_high = c_swing_high_it
        prev_it_swing_low = c_swing_low_it
        it_value = _normalize_step(close_value, bull_it, bear_it, it_norm, norm_smooth)

        bull_lt = False
        bear_lt = False

        c_swing_high_lt = _query_patterns(it_high.last_price, it_high.mid_price, it_high.prev_price, True)
        if c_swing_high_lt and c_swing_high_lt != prev_lt_swing_high and not np.isnan(it_high.mid_price) and it_high.mid_index >= 0:
            _update_pattern(lt_high, it_high.mid_price, it_high.mid_index)

        if not np.isnan(lt_high.last_price) and close_value > lt_high.last_price and not lt_high.is_crossed:
            lt_high.is_crossed = True
            bull_lt = True

        c_swing_low_lt = _query_patterns(it_low.last_price, it_low.mid_price, it_low.prev_price, False)
        if c_swing_low_lt and c_swing_low_lt != prev_lt_swing_low and not np.isnan(it_low.mid_price) and it_low.mid_index >= 0:
            _update_pattern(lt_low, it_low.mid_price, it_low.mid_index)

        if not np.isnan(lt_low.last_price) and close_value < lt_low.last_price and not lt_low.is_crossed:
            lt_low.is_crossed = True
            bear_lt = True

        prev_lt_swing_high = c_swing_high_lt
        prev_lt_swing_low = c_swing_low_lt
        lt_value = _normalize_step(close_value, bull_lt, bear_lt, lt_norm, norm_smooth)

        values = [st_value, it_value, lt_value]
        weights = [weight_k1, weight_k2, weight_k3]
        numerator = 0.0
        denominator = 0.0
        for value, weight in zip(values, weights):
            if not np.isnan(value):
                numerator += weight * value
                denominator += weight

        mso_value = numerator / denominator if denominator > 0 else np.nan

        st_values.append(st_value)
        it_values.append(it_value)
        lt_values.append(lt_value)
        mso_values.append(mso_value)

    mso_series = pd.Series(mso_values, index=df.index, dtype='float64')
    cycle_hist = mso_series - mso_series.ewm(span=cyc_smooth, adjust=False, min_periods=1).mean() + 50.0

    df['mso_st'] = st_values
    df['mso_it'] = it_values
    df['mso_lt'] = lt_values
    df['mso'] = mso_series
    df['cycle_hist'] = cycle_hist

    return df
