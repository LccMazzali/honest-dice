"""
state.py
=============================================================================
GERENCIAMENTO DE ESTADO — Seeds, Nonce e Persistência

Este módulo gerencia o estado interno do bot Honest Dice:
    - Geração e rotação de Server Seeds (entropia de 32 bytes via /dev/urandom)
    - Persistência em disco (JSON) para sobreviver a reinicializações
    - Exposição controlada: o Server Seed NUNCA vaza em logs ou respostas
      do bot; apenas seu hash SHA-256 é mostrado publicamente.

FLUXO DE VIDA DO SERVER SEED:
    1. Bot inicia → verifica se há estado salvo em disco
    2. Se não houver → gera novo Server Seed de 32 bytes, calcula hash
    3. Salva em bot_state.json (apenas o seed, não o hash — o hash é
       derivado)
    4. A cada /rotate_seed:
       a. Server Seed atual → vira "previous_seed" (revelado em texto puro)
       b. Novo Server Seed é gerado
       c. Nonce é resetado para 0
       d. Estado é salvo em disco

SEGURANÇA:
    - Usa secrets.token_hex() do Python, que lê de /dev/urandom (ou
      CryptGenRandom no Windows) — entropia criptograficamente segura
    - O Server Seed NUNCA é enviado em respostas do Discord
    - Apenas SHA-256(server_seed) é exposto → impossível reverter
"""

import json
import os
import secrets
import hashlib
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

STATE_FILE = "bot_state.json"
"""Arquivo onde o estado é persistido em disco."""

SERVER_SEED_BYTES = 32
"""Tamanho do Server Seed em bytes (256 bits de entropia)."""

CLIENT_SEED_BYTES = 16
"""Tamanho do Client Seed padrão em bytes (128 bits)."""


# ---------------------------------------------------------------------------
# Estado em memória (NUNCA exposto diretamente em respostas)
# ---------------------------------------------------------------------------

_state: Dict[str, Any] = {
    "server_seed": None,       # Seed secreta do servidor (NUNCA vazar!)
    "server_seed_hash": None,  # SHA-256(server_seed) — público
    "previous_seed": None,     # Seed anterior (revelada após rotação)
    "client_seed": None,       # Seed pública do cliente
    "nonce": 0,                # Contador incremental de rolagens
    "rolls": 0,                # Total de rolagens acumuladas
}


# ---------------------------------------------------------------------------
# Funções auxiliares de geração criptográfica
# ---------------------------------------------------------------------------

def generate_server_seed() -> str:
    """
    Gera um Server Seed criptograficamente seguro.

    Usa secrets.token_hex() que lê bytes diretamente do gerador de
    números aleatórios do sistema operacional:
        - Linux/macOS: /dev/urandom
        - Windows: CryptGenRandom()

    Returns:
        String hexadecimal de 64 caracteres (32 bytes = 256 bits de entropia)
    """
    return secrets.token_hex(SERVER_SEED_BYTES)


def generate_client_seed() -> str:
    """
    Gera um Client Seed padrão.

    Returns:
        String hexadecimal de 32 caracteres (16 bytes = 128 bits de entropia)
    """
    return secrets.token_hex(CLIENT_SEED_BYTES)


def hash_server_seed(seed: str) -> str:
    """
    Computa SHA-256 do Server Seed para exposição pública.

    Esta hash é o que aparece no footer de cada rolagem. Como SHA-256 é
    uma função de via única (one-way), é computacionalmente inviável
    reverter a hash para descobrir o Server Seed.

    Args:
        seed: O Server Seed em texto plano

    Returns:
        Hash SHA-256 hexadecimal de 64 caracteres
    """
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def load_state() -> None:
    """
    Carrega o estado do disco ou inicializa com seeds frescos.

    Estratégia:
        1. Se o arquivo JSON existe → carrega e valida
        2. Se não existe → gera tudo novo e salva
        3. Se o arquivo está corrompido → fallback para estado fresco

    O Server Seed é carregado do disco, NUNCA é gerado novamente a cada
    inicialização — isso garante continuidade das rolagens.
    """
    global _state

    if not os.path.exists(STATE_FILE):
        _initialize_fresh_state()
        return

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)

        # Valida campos obrigatórios
        required = ["server_seed", "server_seed_hash", "client_seed", "nonce"]
        if not all(k in data for k in required):
            _initialize_fresh_state()
            return

        _state.update(data)

        # Verifica integridade: o hash salvo corresponde ao seed salvo?
        expected_hash = hash_server_seed(_state["server_seed"])
        if _state["server_seed_hash"] != expected_hash:
            # Inconsistência detectada — regenera
            _initialize_fresh_state()

    except (json.JSONDecodeError, IOError, KeyError):
        _initialize_fresh_state()


def _initialize_fresh_state() -> None:
    """Inicializa o estado com seeds completamente novos."""
    new_seed = generate_server_seed()
    _state["server_seed"] = new_seed
    _state["server_seed_hash"] = hash_server_seed(new_seed)
    _state["previous_seed"] = None
    _state["client_seed"] = generate_client_seed()
    _state["nonce"] = 0
    _state["rolls"] = 0
    save_state()


def save_state() -> None:
    """
    Persiste o estado atual em disco (arquivo JSON).

    Chamado após:
        - Cada rolagem (incremento de nonce)
        - Cada rotação de seed
        - Cada mudança de client seed
    """
    with open(STATE_FILE, "w") as f:
        json.dump(_state, f, indent=2)


# ---------------------------------------------------------------------------
# Operações de estado
# ---------------------------------------------------------------------------

def rotate_seed() -> Dict[str, Optional[str]]:
    """
    Rotaciona o Server Seed.

    Fluxo:
        1. Server Seed atual → previous_seed (será revelado publicamente)
        2. Gera NOVO Server Seed de 32 bytes
        3. Calcula SHA-256 do novo seed
        4. Reseta o nonce para 0
        5. Salva em disco

    Returns:
        Dicionário com:
            - "previous_seed": O seed ANTERIOR em texto plano (pode ser
              revelado publicamente)
            - "new_hash": SHA-256 do NOVO seed (para exposição pública)

    Uso:
        Após /rotate_seed, o embed mostra:
        - 🔓 Previous Server Seed: <hex revelado>
        - 🔒 New Server Seed Hash: <SHA-256>
    """
    global _state

    # Preserva o seed atual como "previous" (será revelado)
    _state["previous_seed"] = _state["server_seed"]

    # Gera novo seed
    new_seed = generate_server_seed()
    _state["server_seed"] = new_seed
    _state["server_seed_hash"] = hash_server_seed(new_seed)

    # Reseta nonce para a nova sessão
    _state["nonce"] = 0

    save_state()

    return {
        "previous_seed": _state["previous_seed"],
        "new_hash": _state["server_seed_hash"],
    }


def get_state() -> Dict[str, Any]:
    """
    Retorna o estado atual (APENAS informações públicas).

    Esta função NUNCA inclui o server_seed atual. Apenas:
        - server_seed_hash (público)
        - previous_seed (já revelado)
        - client_seed (público)
        - nonce (público)
        - rolls (público)

    Returns:
        Dicionário com informações públicas do estado
    """
    return {
        "server_seed_hash": _state["server_seed_hash"],
        "previous_seed": _state["previous_seed"],
        "client_seed": _state["client_seed"],
        "nonce": _state["nonce"],
        "rolls": _state["rolls"],
    }


def get_server_seed() -> str:
    """
    Retorna o Server Seed atual (USO INTERNO — NUNCA expor em respostas).

    Esta função é chamada APENAS pelo módulo dice/roller.py para gerar
    as rolagens. O seed NUNCA aparece em embeds, logs, ou saída do bot.

    Returns:
        String hexadecimal de 64 caracteres
    """
    return _state["server_seed"]


def get_client_seed() -> str:
    """Retorna o Client Seed atual."""
    return _state["client_seed"]


def set_client_seed(seed: str) -> None:
    """
    Define um novo Client Seed fornecido pelo usuário.

    Quando o usuário muda o Client Seed, o nonce é resetado para 0.
    Isso permite que o usuário controle parte da entropia do sistema.

    Args:
        seed: String personalizada (mín. 4, máx. 64 caracteres)
    """
    _state["client_seed"] = seed
    _state["nonce"] = 0
    save_state()


def get_nonce() -> int:
    """Retorna o nonce atual (próximo valor a ser usado)."""
    return _state["nonce"]


def increment_nonce() -> None:
    """
    Incrementa o nonce em +1 e salva o estado.

    Chamado a CADA rolagem individual de dado. Garante que cada rolagem
    produza um resultado HMAC único.
    """
    _state["nonce"] += 1
    _state["rolls"] += 1
    save_state()