"""分析引擎 —— 技术指标计算 + 基本面分析"""

import pandas as pd
import numpy as np


def calculate_ma(data: pd.Series, window: int) -> pd.Series:
    """计算移动平均线"""
    return data.rolling(window=window).mean()


def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """计算 MACD 指标"""
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar


def calculate_rsi(data: pd.Series, window: int = 14) -> pd.Series:
    """计算 RSI 指标"""
    delta = data.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_kdj(data_high: pd.Series, data_low: pd.Series, data_close: pd.Series,
                   window: int = 9):
    """计算 KDJ 指标"""
    low_min = data_low.rolling(window=window).min()
    high_max = data_high.rolling(window=window).max()
    rsv = 100 * (data_close - low_min) / (high_max - low_min + 1e-10)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def calculate_boll(data: pd.Series, window: int = 20, num_std: int = 2):
    """计算布林带"""
    ma = data.rolling(window=window).mean()
    std = data.rolling(window=window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return upper, ma, lower


def generate_signals(dif: pd.Series, dea: pd.Series, rsi: pd.Series,
                      k: pd.Series, d: pd.Series) -> str:
    """综合生成买卖信号"""
    signals = []

    # MACD 信号
    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
        signals.append("MACD金叉")
    elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
        signals.append("MACD死叉")

    # RSI 信号
    rsi_val = rsi.iloc[-1]
    if rsi_val > 80:
        signals.append("RSI超买")
    elif rsi_val < 20:
        signals.append("RSI超卖")

    # KDJ 信号
    if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
        signals.append("KDJ金叉")
    elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
        signals.append("KDJ死叉")

    if not signals:
        return "持有"
    return " / ".join(signals)
