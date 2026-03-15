import pandas as pd
import numpy as np

def calculate_normalized_macd(df: pd.DataFrame, fast=12, slow=26, signal=9, norm_len=200, norm_smooth=3):
    # Calculate regular MACD
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    
    # Normalize MACD to 0-100 like in TradingView script
    lowest_macd = macd.rolling(window=norm_len, min_periods=1).min()
    highest_macd = macd.rolling(window=norm_len, min_periods=1).max()
    
    # Avoid division by zero
    diff = highest_macd - lowest_macd
    diff = diff.replace(0, 1) # just to avoid inf
    
    norm = ((macd - lowest_macd) / diff) * 100.0
    
    # Smooth with SMA
    macd_norm_smoothed = norm.rolling(window=norm_smooth, min_periods=1).mean()
    
    df['macd_norm'] = macd_norm_smoothed
    
    # Calculate signal line for the regular MACD and then normalize it? 
    # Or just use MACD cross based on the raw MACD or normalized MACD.
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    df['macd_raw'] = macd
    df['macd_signal_raw'] = macd_signal
    
    return df

def calculate_mso(df: pd.DataFrame, smooth=4):
    """
    Market Structure Oscillator (Simplified Python Translation)
    This matches the general logic of finding broken swing highs (bullish) and broken swing lows (bearish).
    We'll do a simplified normalization.
    """
    # Find simple swing highs and lows (3 bar pattern)
    swing_highs = (df['high'].shift(1) > df['high'].shift(2)) & (df['high'].shift(1) >= df['high'])
    swing_lows = (df['low'].shift(1) < df['low'].shift(2)) & (df['low'].shift(1) <= df['low'])
    
    # Keep track of last swing high and low values
    df['last_swing_high'] = np.where(swing_highs, df['high'].shift(1), np.nan)
    df['last_swing_high'] = df['last_swing_high'].ffill()
    
    df['last_swing_low'] = np.where(swing_lows, df['low'].shift(1), np.nan)
    df['last_swing_low'] = df['last_swing_low'].ffill()
    
    bull = df['close'] > df['last_swing_high']
    bear = df['close'] < df['last_swing_low']
    
    # State tracking
    os_state = pd.Series(0, index=df.index)
    current_os = 0
    
    # We must iterate for the specific state logic
    bull_arr = bull.values
    bear_arr = bear.values
    close_arr = df['close'].values
    
    max_val = np.nan
    min_val = np.nan
    
    os_list = []
    mso_raw = []
    
    for i in range(len(df)):
        if bull_arr[i]:
            current_os = 1
        elif bear_arr[i]:
            current_os = -1
            
        os_list.append(current_os)
        
        # PineScript logic for Max/Min:
        # max_val = os > os[1] ? close : os < os[1] ? max_val : max(close, max_val)
        if i == 0:
            max_val = close_arr[i]
            min_val = close_arr[i]
        else:
            prev_os = os_list[i-1]
            if current_os > prev_os:
                max_val = close_arr[i]
                min_val = min_val # os > os[1] ? min : unchanged wait, PineScript says:
                # min_val = os < os[1] ? close : os > os[1] ? min : min(close, min)
            elif current_os < prev_os:
                min_val = close_arr[i]
            else:
                max_val = max(close_arr[i], max_val if not np.isnan(max_val) else close_arr[i])
                min_val = min(close_arr[i], min_val if not np.isnan(min_val) else close_arr[i])
        
        if np.isnan(max_val) or np.isnan(min_val) or max_val == min_val:
            mso_raw.append(50.0)
        else:
            val = (close_arr[i] - min_val) / (max_val - min_val) * 100.0
            mso_raw.append(val)
            
    df['mso_raw'] = mso_raw
    # Smooth with SMA
    df['mso'] = df['mso_raw'].rolling(window=smooth, min_periods=1).mean()
    
    return df
