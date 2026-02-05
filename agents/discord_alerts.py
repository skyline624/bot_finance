"""Discord integration for trading alerts."""

import asyncio
from typing import Optional
from datetime import datetime
import aiohttp

from config import get_settings
from .signal_generator import SignalTrading

settings = get_settings()


def format_alert_message(signal: SignalTrading) -> dict:
    """
    Format a trading signal as a Discord embed.

    Args:
        signal: The trading signal to format

    Returns:
        Discord webhook payload dictionary
    """
    # Color based on action
    color_map = {
        "ACHAT_FORT": 0x00FF00,  # Bright green
        "ACHAT": 0x90EE90,  # Light green
        "NEUTRE": 0xFFD700,  # Gold
        "VENTE": 0xFF6B6B,  # Light red
        "VENTE_FORTE": 0xFF0000,  # Bright red
    }

    color = color_map.get(signal.action, 0x808080)

    # Emoji based on action
    emoji_map = {
        "ACHAT_FORT": "🚀",
        "ACHAT": "📈",
        "NEUTRE": "➖",
        "VENTE": "📉",
        "VENTE_FORTE": "🔻",
    }

    emoji = emoji_map.get(signal.action, "❓")

    fields = [
        {
            "name": "💰 Prix d'entrée",
            "value": f"{signal.prix_entree:.2f}",
            "inline": True,
        },
        {
            "name": "🎯 Confiance",
            "value": f"{signal.confiance:.0%}",
            "inline": True,
        },
    ]

    if signal.stop_loss:
        fields.append({
            "name": "🛑 Stop Loss",
            "value": f"{signal.stop_loss:.2f}",
            "inline": True,
        })

    if signal.take_profit:
        fields.append({
            "name": "✅ Take Profit",
            "value": f"{signal.take_profit:.2f}",
            "inline": True,
        })

    embed = {
        "title": f"{emoji} Signal Trading: {signal.ticker}",
        "description": f"**Action recommandée:** {signal.action}",
        "color": color,
        "fields": fields,
        "footer": {
            "text": f"Bot Finance AI • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        },
        "timestamp": datetime.now().isoformat(),
    }

    return {"embeds": [embed]}


async def send_discord_alert_async(signal: SignalTrading, webhook_url: Optional[str] = None) -> bool:
    """
    Send a trading alert to Discord asynchronously.

    Args:
        signal: The trading signal to send
        webhook_url: Optional custom webhook URL

    Returns:
        True if sent successfully, False otherwise
    """
    url = webhook_url or settings.DISCORD_WEBHOOK_URL

    if not url:
        print("⚠️ [DISCORD] Aucun webhook configuré")
        return False

    payload = format_alert_message(signal)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 204:
                    print(f"   ✅ [DISCORD] Alerte envoyée pour {signal.ticker}")
                    return True
                else:
                    print(f"   ⚠️ [DISCORD] Erreur HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"   ❌ [DISCORD] Erreur: {str(e)}")
        return False


def send_discord_alert(signal: SignalTrading, webhook_url: Optional[str] = None) -> bool:
    """
    Send a trading alert to Discord (sync wrapper).

    Args:
        signal: The trading signal to send
        webhook_url: Optional custom webhook URL

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        return asyncio.run(send_discord_alert_async(signal, webhook_url))
    except RuntimeError:
        # If already in async context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(send_discord_alert_async(signal, webhook_url))


async def send_multiple_alerts(signals: list[SignalTrading], webhook_url: Optional[str] = None) -> list[bool]:
    """
    Send multiple alerts to Discord concurrently.

    Args:
        signals: List of trading signals
        webhook_url: Optional custom webhook URL

    Returns:
        List of success booleans
    """
    tasks = [send_discord_alert_async(signal, webhook_url) for signal in signals]
    return await asyncio.gather(*tasks)


def format_summary_message(signals: list[SignalTrading]) -> dict:
    """
    Format a summary of all signals for Discord.

    Args:
        signals: List of trading signals

    Returns:
        Discord webhook payload dictionary
    """
    # Count signals by type
    achat_fort = sum(1 for s in signals if s.action == "ACHAT_FORT")
    achat = sum(1 for s in signals if s.action == "ACHAT")
    neutre = sum(1 for s in signals if s.action == "NEUTRE")
    vente = sum(1 for s in signals if s.action == "VENTE")
    vente_forte = sum(1 for s in signals if s.action == "VENTE_FORTE")

    # Build signal list
    signal_lines = []
    for signal in signals:
        emoji = {
            "ACHAT_FORT": "🚀",
            "ACHAT": "📈",
            "NEUTRE": "➖",
            "VENTE": "📉",
            "VENTE_FORTE": "🔻",
        }.get(signal.action, "❓")

        signal_lines.append(f"{emoji} **{signal.ticker}**: {signal.action} (confiance: {signal.confiance:.0%})")

    description = f"""**Résumé des Signaux:**
🚀 ACHAT_FORT: {achat_fort} | 📈 ACHAT: {achat} | ➖ NEUTRE: {neutre} | 📉 VENTE: {vente} | 🔻 VENTE_FORTE: {vente_forte}

**Détails:**
{chr(10).join(signal_lines)}
"""

    embed = {
        "title": "📊 Rapport Trading - Métaux Précieux",
        "description": description,
        "color": 0xFFD700,  # Gold
        "footer": {
            "text": f"Bot Finance AI • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        },
        "timestamp": datetime.now().isoformat(),
    }

    return {"embeds": [embed]}


async def send_summary_to_discord(signals: list[SignalTrading], webhook_url: Optional[str] = None) -> bool:
    """
    Send a summary of all signals to Discord.

    Args:
        signals: List of trading signals
        webhook_url: Optional custom webhook URL

    Returns:
        True if sent successfully
    """
    url = webhook_url or settings.DISCORD_WEBHOOK_URL

    if not url:
        print("⚠️ [DISCORD] Aucun webhook configuré")
        return False

    payload = format_summary_message(signals)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 204:
                    print("   ✅ [DISCORD] Résumé envoyé")
                    return True
                else:
                    print(f"   ⚠️ [DISCORD] Erreur HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"   ❌ [DISCORD] Erreur: {str(e)}")
        return False
