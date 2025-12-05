"""
Message formatters for Telegram bot output.
Bloomberg-style terminal display.
"""
from .models import Token, Pool, SafetyLevel
from datetime import datetime


def format_terminal_header() -> str:
    """Terminal-style header."""
    return (
        "```\n"
        "╔══════════════════════════════════════════╗\n"
        "║     MEMESCAN - TON Meme Terminal         ║\n"
        "╚══════════════════════════════════════════╝\n"
        "```"
    )


def format_trending(tokens: list[Token]) -> str:
    """Format trending tokens list."""
    if not tokens:
        return "No trending tokens found."

    lines = [format_terminal_header(), "", "**🔥 TRENDING NOW**", ""]

    for i, token in enumerate(tokens[:10], 1):
        change_emoji = "📈" if token.price_change_24h >= 0 else "📉"
        lines.append(
            f"`{i:2d}.` **{token.symbol}** "
            f"{change_emoji} {token.format_change()} "
            f"| ${_format_compact(token.volume_24h_usd)} vol"
        )

    lines.append("")
    lines.append(f"_Updated: {datetime.utcnow().strftime('%H:%M UTC')}_")
    return "\n".join(lines)


def format_new_launches(tokens: list[Token]) -> str:
    """Format new token launches."""
    if not tokens:
        return "No new launches found."

    lines = [format_terminal_header(), "", "**🆕 NEW LAUNCHES**", ""]

    for token in tokens[:10]:
        age = _format_age(token.created_at) if token.created_at else "?"
        liq = _format_compact(token.liquidity_usd)

        lines.append(
            f"• **{token.symbol}** | "
            f"{age} | "
            f"${liq} liq"
        )

    lines.append("")
    lines.append("_Use /check <address> for safety analysis_")
    return "\n".join(lines)


def format_token_analysis(token: Token) -> str:
    """Format detailed token safety analysis."""
    lines = [
        format_terminal_header(),
        "",
        f"**{token.safety_emoji()} {token.symbol}** - {token.name}",
        "",
        "```",
        f"Address:     {token.address[:8]}...{token.address[-6:]}",
        f"Holders:     {token.holder_count:,}",
        f"Top Wallet:  {token.dev_wallet_percent:.1f}%",
        "```",
        "",
    ]

    # Safety verdict
    if token.safety_level == SafetyLevel.SAFE:
        lines.append("**VERDICT: ✅ RELATIVELY SAFE**")
    elif token.safety_level == SafetyLevel.WARNING:
        lines.append("**VERDICT: ⚠️ PROCEED WITH CAUTION**")
    elif token.safety_level == SafetyLevel.DANGER:
        lines.append("**VERDICT: 🚨 HIGH RISK**")
    else:
        lines.append("**VERDICT: ❓ UNKNOWN**")

    # Warnings
    if token.safety_warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for warning in token.safety_warnings:
            lines.append(f"  {warning}")

    return "\n".join(lines)


def format_top_pools(pools: list[Pool]) -> str:
    """Format top liquidity pools."""
    if not pools:
        return "No pools found."

    lines = [format_terminal_header(), "", "**💧 TOP POOLS**", ""]

    for i, pool in enumerate(pools[:10], 1):
        pair = f"{pool.token0_symbol}/{pool.token1_symbol}"
        liq = _format_compact(pool.liquidity_usd)

        lines.append(
            f"`{i:2d}.` **{pair}** | "
            f"${liq} TVL | "
            f"{pool.dex.upper()}"
        )

    return "\n".join(lines)


def format_stats_summary(stats: dict) -> str:
    """Format DEX statistics summary."""
    lines = [
        format_terminal_header(),
        "",
        "**📊 TON DEX STATS**",
        "",
        "```",
        f"24h Volume:  ${_format_compact(stats.get('volume_24h', 0))}",
        f"Total TVL:   ${_format_compact(stats.get('tvl', 0))}",
        f"Tokens:      {stats.get('token_count', 0):,}",
        f"Pools:       {stats.get('pool_count', 0):,}",
        "```",
    ]
    return "\n".join(lines)


def _format_compact(value: float) -> str:
    """Format large numbers compactly."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def _format_age(dt: datetime) -> str:
    """Format datetime as age string."""
    if not dt:
        return "?"

    now = datetime.utcnow()
    # Handle timezone-aware datetimes
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h"
    return f"{delta.days}d"
