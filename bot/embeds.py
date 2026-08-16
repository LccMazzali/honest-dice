"""
embeds.py
=============================================================================
FORMATAÇÃO DE EMBEDS

Formato padrão:

🎲 2d6+1d4+3

.2d6 [4 + 2] = 6
.1d4 = 3
.+4+3=+7
Total = 9 💀
"""

import discord
from typing import Dict, List, Optional

from dice.roller import RollResult, RollGroup, IndividualRoll


# ===========================================================================
# CORES
# ===========================================================================

CRITICAL_SUCCESS_COLOR = 0x00FF00
CRITICAL_FAIL_COLOR    = 0xFF0000
NORMAL_COLOR           = 0x5865F2
CRITICAL_MIXED_COLOR   = 0xFFAA00


# ===========================================================================
# HELPERS
# ===========================================================================

def _has_cs(result: RollResult) -> bool:
    return any(r.is_critical_success for g in result.groups for r in g.kept_rolls)

def _has_cf(result: RollResult) -> bool:
    return any(r.is_critical_fail for g in result.groups for r in g.kept_rolls)


# ===========================================================================
# EMBED PRINCIPAL
# ===========================================================================

def format_roll_embed(result: RollResult, ephemeral: bool = False,
                      history_id: Optional[int] = None) -> discord.Embed:
    cs = _has_cs(result)
    cf = _has_cf(result)

    if cs and cf:
        color = CRITICAL_MIXED_COLOR
    elif cs:
        color = CRITICAL_SUCCESS_COLOR
    elif cf:
        color = CRITICAL_FAIL_COLOR
    else:
        color = NORMAL_COLOR

    # Monta as linhas de resultado
    lines = []
    for group in result.groups:
        label = f".{group.count}d{group.faces}"
        if group.kept_count < group.count:
            avg_k = sum(r.value for r in group.kept_rolls) / len(group.kept_rolls) if group.kept_rolls else 0
            avg_a = sum(r.value for r in group.rolls) / len(group.rolls) if group.rolls else 0
            mode = "kh" if avg_k > avg_a else "kl"
            label += f"{mode}{group.kept_count}"

        # Valores SEM formatação de crítico (só números)
        vals = [str(r.value) for r in group.rolls]
        for r in group.rolls:
            if not r.kept:
                vals.append(f"~~{r.value}~~")

        # Reconstrói vals na ordem correta com descartados riscados
        vals = []
        for r in group.rolls:
            if not r.kept:
                vals.append(f"~~{r.value}~~")
            else:
                vals.append(str(r.value))

        vals_str = " + ".join(vals)

        if group.count > 1:
            lines.append(f"{label} [{vals_str}] = {group.total}")
        else:
            lines.append(f"{label} = {group.rolls[0].value}")

    # Modificador plano: mostra a soma dos componentes
    if result.flat_modifier != 0:
        parts = result.flat_modifier_parts if hasattr(result, 'flat_modifier_parts') and result.flat_modifier_parts else []
        if parts:
            # Mostra cada parte: +4+3=+7  ou -3-2=-5
            parts_str = "".join(f"+{p}" if p > 0 else str(p) for p in parts)
            total_str = f"+{result.flat_modifier}" if result.flat_modifier > 0 else str(result.flat_modifier)
            lines.append(f".{parts_str}={total_str}")
        else:
            s = "+" if result.flat_modifier > 0 else ""
            lines.append(f".{s}{result.flat_modifier}")

    # Total
    mark = ""
    if cs and cf:
        mark = " ⚖️"
    elif cs:
        mark = " 🎉"
    elif cf:
        mark = " 💀"

    lines.append(f"Total = {result.grand_total}{mark}")

    desc = "\n".join(lines)

    embed = discord.Embed(
        title=f"🎲 {result.expression}",
        description=desc,
        color=color,
    )

    return embed


# ===========================================================================
# DEMAIS EMBEDS
# ===========================================================================

def format_history_embed(entries: List[Dict], is_admin: bool = False,
                         user_id: Optional[int] = None) -> discord.Embed:
    if not entries:
        return discord.Embed(title="📜 Histórico", description="Vazio.", color=NORMAL_COLOR)
    lines = []
    for entry in entries:
        from datetime import datetime
        ts = datetime.fromtimestamp(entry.get("timestamp", 0)).strftime("%d/%m %H:%M")
        p = f"`{entry['user_name']}` " if is_admin else ""
        hc = any(r["crit_success"] or r["crit_fail"] for g in entry["groups"] for r in g["rolls"])
        cm = " ⚠️" if hc else ""
        lines.append(f"{p}`#{entry['id']:3d}` {ts}  `{entry['expression']:10s}` → **{entry['grand_total']:3d}**{cm}  🆔{entry['nonce']}")
    embed = discord.Embed(
        title="📜 Seu Histórico" if not is_admin else "📜 Histórico do Servidor",
        description="```\n" + "\n".join(lines) + "\n```",
        color=NORMAL_COLOR,
    )
    embed.set_footer(text=f"{len(entries)} rolagens | /verify")
    return embed


def format_rotation_embed(previous_seed: str, new_hash: str) -> discord.Embed:
    embed = discord.Embed(title="🔄 Server Seed", description="Seed anterior revelado.", color=0x9B59B6)
    embed.add_field(name="🔓 Anterior", value=f"```\n{previous_seed}\n```", inline=False)
    embed.add_field(name="🔒 Novo Hash", value=f"`{new_hash}`", inline=False)
    embed.set_footer(text="Honest Dice — Provably Fair")
    return embed


def format_status_embed(state: dict) -> discord.Embed:
    embed = discord.Embed(title="🔒 Honest Dice", color=NORMAL_COLOR)
    embed.add_field(name="🔒 Seed Hash", value=f"`{state['server_seed_hash'][:20]}..`", inline=False)
    embed.add_field(name="🔑 Client Seed", value=f"`{state['client_seed'][:12]}..`", inline=True)
    embed.add_field(name="🆔 Nonce", value=f"`{state['nonce']}`", inline=True)
    embed.add_field(name="📊 Rolagens", value=f"`{state['rolls']}`", inline=True)
    if state.get("previous_seed"):
        embed.add_field(name="📜 Última Revelação", value=f"`{state['previous_seed'][:12]}..`", inline=False)
    embed.set_footer(text="/rotate_seed")
    return embed


def format_verify_embed(is_valid: bool, server_seed: str, client_seed: str,
                        nonce: int, faces: int, result: int) -> discord.Embed:
    color = 0x00FF00 if is_valid else 0xFF0000
    embed = discord.Embed(
        title="🔍 Verificação",
        description=f"**Seed:** `{server_seed[:12]}..{server_seed[-6:]}`  **Client:** `{client_seed}`  **Nonce:** `{nonce}`  **d{faces}** → **{result}**",
        color=color,
    )
    embed.add_field(
        name="✅ VÁLIDO" if is_valid else "❌ INVÁLIDO",
        value="HMAC-SHA256 confere." if is_valid else "Não confere — verifique os parâmetros.",
        inline=False,
    )
    return embed