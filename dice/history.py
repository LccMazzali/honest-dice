"""
history.py
=============================================================================
HISTÓRICO DE ROLAGENS — Armazenamento e consulta por servidor

Este módulo gerencia o histórico persistente de rolagens para cada servidor
Discord onde o bot Honest Dice opera.

ESTRUTURA DE ARMAZENAMENTO:
    Um arquivo JSON por servidor (history_{guild_id}.json):
    {
        "next_id": 1,              # Auto-incremento do ID local
        "entries": [
            {
                "id": 1,           # ID sequencial por servidor
                "user_id": "1234567890",
                "user_name": "Jogador#1234",
                "expression": "1d20+5",
                "grand_total": 25,
                "groups": [...],   # Dados compactos dos grupos rolados
                "nonce": 42,
                "seed_hash": "a1b2...",
                "timestamp": 1234567890.0
            },
            ...
        ]
    }

LIMITES:
    - Máximo de 50 entradas por servidor
    - Entradas mais antigas são removidas quando o limite é atingido
    - O arquivo é criado automaticamente na primeira rolagem de cada servidor
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dice.roller import RollResult, RollGroup, IndividualRoll

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

HISTORY_DIR = Path("history")
"""Diretório onde os arquivos de histórico são armazenados."""

MAX_ENTRIES_PER_GUILD = 50
"""Número máximo de entradas de histórico por servidor."""

HISTORY_FILE_PREFIX = "history_"
HISTORY_FILE_SUFFIX = ".json"


# ---------------------------------------------------------------------------
# Funções auxiliares de arquivo
# ---------------------------------------------------------------------------

def _ensure_history_dir() -> None:
    """Garante que o diretório de histórico existe."""
    HISTORY_DIR.mkdir(exist_ok=True)


def _guild_file_path(guild_id: int) -> Path:
    """
    Retorna o caminho completo para o arquivo de histórico de um servidor.

    Args:
        guild_id: ID do servidor Discord

    Returns:
        Path para o arquivo history_{guild_id}.json
    """
    return HISTORY_DIR / f"{HISTORY_FILE_PREFIX}{guild_id}{HISTORY_FILE_SUFFIX}"


def _load_guild_history(guild_id: int) -> Dict[str, Any]:
    """
    Carrega o histórico de um servidor do disco.

    Se o arquivo não existir, retorna um dicionário vazio.

    Args:
        guild_id: ID do servidor Discord

    Returns:
        Dicionário com "entries" (lista) e "next_id" (int)
    """
    _ensure_history_dir()
    file_path = _guild_file_path(guild_id)

    if not file_path.exists():
        return {"entries": [], "next_id": 1}

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            # Garante que os campos obrigatórios existam
            if "entries" not in data:
                data["entries"] = []
            if "next_id" not in data:
                data["next_id"] = 1
            return data
    except (json.JSONDecodeError, IOError):
        return {"entries": [], "next_id": 1}


def _save_guild_history(guild_id: int, data: Dict[str, Any]) -> None:
    """
    Salva o histórico de um servidor no disco.

    Args:
        guild_id: ID do servidor Discord
        data:     Dicionário com "entries" e "next_id"
    """
    _ensure_history_dir()
    file_path = _guild_file_path(guild_id)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def _compact_roll(roll: IndividualRoll) -> Dict[str, Any]:
    """
    Converte um IndividualRoll para formato compacto de armazenamento.

    Args:
        roll: Rolagem individual

    Returns:
        Dicionário com os dados essenciais
    """
    return {
        "face": roll.faces,
        "value": roll.value,
        "crit_fail": roll.is_critical_fail,
        "crit_success": roll.is_critical_success,
        "kept": roll.kept,
    }


def _compact_group(group: RollGroup) -> Dict[str, Any]:
    """
    Converte um RollGroup para formato compacto de armazenamento.

    Args:
        group: Grupo de dados rolados

    Returns:
        Dicionário com os dados essenciais do grupo
    """
    return {
        "count": group.count,
        "faces": group.faces,
        "modifier": group.modifier,
        "rolls": [_compact_roll(r) for r in group.rolls],
        "total": group.total,
        "modifier_total": group.modifier_total,
        "kept_count": group.kept_count,
        "kept_roll_values": [r.value for r in group.kept_rolls],
    }


# ---------------------------------------------------------------------------
# Funções públicas da API de histórico
# ---------------------------------------------------------------------------

def add_entry(guild_id: int, user_id: int, user_name: str,
              result: RollResult) -> int:
    """
    Adiciona uma entrada de rolagem ao histórico de um servidor.

    Gerencia automaticamente o limite de 50 entradas: quando o limite é
    atingido, a entrada mais antiga é removida para abrir espaço.

    Args:
        guild_id:  ID do servidor Discord
        user_id:   ID do usuário que rolou
        user_name: Nome de exibição do usuário (ex: "Player#1234")
        result:    Objeto RollResult com os dados da rolagem

    Returns:
        O ID numérico da entrada no histórico (para referência no embed)
    """
    data = _load_guild_history(guild_id)

    entry_id = data["next_id"]

    # Constrói a entrada
    entry = {
        "id": entry_id,
        "user_id": str(user_id),
        "user_name": user_name,
        "expression": result.expression,
        "grand_total": result.grand_total,
        "groups": [_compact_group(g) for g in result.groups],
        "flat_modifier": result.flat_modifier,
        "nonce": result.nonce,
        "seed_hash": result.server_seed_hash,
        "timestamp": time.time(),
    }

    data["entries"].append(entry)
    data["next_id"] = entry_id + 1

    # Gerencia o limite: remove as entradas mais antigas
    while len(data["entries"]) > MAX_ENTRIES_PER_GUILD:
        data["entries"].pop(0)

    _save_guild_history(guild_id, data)

    return entry_id


def get_user_history(guild_id: int, user_id: int,
                     limit: int = 25) -> List[Dict[str, Any]]:
    """
    Retorna o histórico de rolagens de um usuário específico.

    Args:
        guild_id: ID do servidor Discord
        user_id:  ID do usuário
        limit:    Número máximo de entradas a retornar (padrão: 25)

    Returns:
        Lista de entradas de histórico (mais recentes primeiro)
    """
    data = _load_guild_history(guild_id)

    # Filtra por usuário e ordena do mais recente para o mais antigo
    user_entries = [
        e for e in data["entries"]
        if e["user_id"] == str(user_id)
    ]

    # Retorna as últimas 'limit' entradas (mais recentes primeiro)
    return user_entries[-limit:][::-1]


def get_guild_history(guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retorna o histórico completo de rolagens de um servidor.

    Esta função é destinada a administradores, que podem ver todas as
    rolagens de todos os usuários.

    Args:
        guild_id: ID do servidor Discord
        limit:    Número máximo de entradas a retornar (padrão: 50)

    Returns:
        Lista de entradas de histórico (mais recentes primeiro)
    """
    data = _load_guild_history(guild_id)

    # Retorna as últimas 'limit' entradas (mais recentes primeiro)
    return data["entries"][-limit:][::-1]


def get_entry(guild_id: int, entry_id: int) -> Optional[Dict[str, Any]]:
    """
    Retorna uma entrada específica do histórico pelo seu ID.

    Args:
        guild_id: ID do servidor Discord
        entry_id: ID da entrada no histórico

    Returns:
        A entrada do histórico, ou None se não encontrada
    """
    data = _load_guild_history(guild_id)

    for entry in data["entries"]:
        if entry["id"] == entry_id:
            return entry

    return None


def get_stats(guild_id: int) -> Dict[str, Any]:
    """
    Retorna estatísticas básicas do histórico de um servidor.

    Args:
        guild_id: ID do servidor Discord

    Returns:
        Dicionário com:
            - total_entries: número total de entradas
            - unique_users:  número de usuários únicos que rolaram
            - oldest:        timestamp da entrada mais antiga
            - newest:        timestamp da entrada mais recente
    """
    data = _load_guild_history(guild_id)
    entries = data["entries"]

    if not entries:
        return {
            "total_entries": 0,
            "unique_users": 0,
            "oldest": None,
            "newest": None,
        }

    unique_users = len(set(e["user_id"] for e in entries))

    return {
        "total_entries": len(entries),
        "unique_users": unique_users,
        "oldest": entries[0]["timestamp"],
        "newest": entries[-1]["timestamp"],
    }