"""Technical analysis tools for trading signals."""

from typing import Dict, Any

from config import get_settings

settings = get_settings()


def calculate_pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
    """
    Calculate classic pivot points (P, R1, S1, R2, S2).

    Args:
        high: High price
        low: Low price
        close: Close price

    Returns:
        Dictionary with pivot point levels
    """
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)

    return {
        "pivot": pivot,
        "r1": r1,
        "s1": s1,
        "r2": r2,
        "s2": s2,
    }


def analyze_technicals(market_data: Dict[str, Any]) -> str:
    """
    Analyze technical indicators and generate interpretation.

    Args:
        market_data: Dictionary with market data and indicators

    Returns:
        Technical analysis summary string
    """
    if "error" in market_data:
        return f"Erreur: {market_data['error']}"

    ticker = market_data.get("ticker", "Unknown")
    current = market_data.get("current_price", 0)
    rsi = market_data.get("rsi", 50)
    sma200 = market_data.get("sma200", current)
    sma50 = market_data.get("sma50", current)
    macd = market_data.get("macd", 0)
    macd_signal = market_data.get("macd_signal", 0)
    r1 = market_data.get("r1", 0)
    s1 = market_data.get("s1", 0)
    pivot = market_data.get("pivot", 0)
    bb_upper = market_data.get("bb_upper", 0)
    bb_lower = market_data.get("bb_lower", 0)

    # RSI Analysis
    if rsi > settings.RSI_OVERBOUGHT:
        rsi_signal = "SURACHAT (Bearish)"
    elif rsi < settings.RSI_OVERSOLD:
        rsi_signal = "SURVENTE (Bullish)"
    else:
        rsi_signal = "NEUTRE"

    # Trend Analysis (Price vs SMA200)
    if current > sma200:
        trend = "HAUSSIÈRE (au-dessus SMA200)"
    else:
        trend = "BAISSIÈRE (sous SMA200)"

    # Golden/Death Cross (SMA50 vs SMA200)
    if sma50 > sma200:
        cross_signal = "GOLDEN CROSS (Bullish)"
    else:
        cross_signal = "DEATH CROSS (Bearish)"

    # MACD Signal
    if macd > macd_signal:
        macd_signal_text = "HAUSSIER (MACD > Signal)"
    else:
        macd_signal_text = "BAISSIER (MACD < Signal)"

    # Bollinger Bands Position
    if current >= bb_upper:
        bb_position = "SURACHAT (touch bande supérieure)"
    elif current <= bb_lower:
        bb_position = "SURVENTE (touch bande inférieure)"
    else:
        bb_position = "DANS LES BANDES (normal)"

    # Pivot Points Proximity
    distance_to_r1 = abs(r1 - current) / current * 100 if current > 0 else 0
    distance_to_s1 = abs(s1 - current) / current * 100 if current > 0 else 0

    if distance_to_r1 < 1:
        pivot_signal = f"PROCHE RÉSISTANCE R1 ({distance_to_r1:.2f}%)"
    elif distance_to_s1 < 1:
        pivot_signal = f"PROCHE SUPPORT S1 ({distance_to_s1:.2f}%) - Zone d'achat"
    else:
        pivot_signal = "En zone neutre"

    analysis = f"""
    ANALYSE TECHNIQUE {ticker}:
    ─────────────────────────────────────────
    PRIX ACTUEL: {current:.2f}

    [TENDANCE]
    - Direction: {trend}
    - SMA50 vs SMA200: {cross_signal}

    [MOMENTUM]
    - RSI ({settings.RSI_PERIOD}): {rsi:.2f} → {rsi_signal}
    - MACD: {macd:.4f} vs Signal: {macd_signal:.4f} → {macd_signal_text}

    [VOLATILITÉ]
    - Position BB: {bb_position}

    [NIVEAUX CLÉS]
    - Résistance R1: {r1:.2f} ({distance_to_r1:.2f}% du prix)
    - Pivot Central: {pivot:.2f}
    - Support S1: {s1:.2f} ({distance_to_s1:.2f}% du prix)
    - Signal Pivot: {pivot_signal}
    """

    return analysis


def get_technical_signals(market_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract structured signals from technical analysis.

    Args:
        market_data: Dictionary with market data

    Returns:
        Dictionary with boolean signals for each indicator
    """
    if "error" in market_data:
        return {"error": market_data["error"]}

    current = market_data.get("current_price", 0)
    rsi = market_data.get("rsi", 50)
    sma200 = market_data.get("sma200", current)
    sma50 = market_data.get("sma50", current)
    macd = market_data.get("macd", 0)
    macd_signal = market_data.get("macd_signal", 0)
    s1 = market_data.get("s1", 0)

    # Calculate distance to support
    distance_to_s1 = abs(s1 - current) / current * 100 if current > 0 else 100

    return {
        "rsi_bullish": rsi < settings.RSI_OVERSOLD,
        "rsi_bearish": rsi > settings.RSI_OVERBOUGHT,
        "trend_bullish": current > sma200,
        "golden_cross": sma50 > sma200,
        "macd_bullish": macd > macd_signal,
        "near_support": distance_to_s1 < 2,  # Within 2% of S1
        "near_support_distance": distance_to_s1,
    }
