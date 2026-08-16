"""
provably_fair.py
=============================================================================
NÚCLEO CRIPTOGRÁFICO — Gerador de Números Aleatórios Provably Fair

Este módulo implementa o coração do sistema Honest Dice: um RNG (Random
Number Generator) deterministico e verificável que elimina a necessidade de
confiar cegamente no servidor.

ARQUITETURA:
    HMAC-SHA256(key=ServerSeed, message=ClientSeed:Nonce)
                                    |
                            [32 bytes / 64 hex chars]
                                    |
                        Rejection Sampling (eliminação de bias)
                                    |
                            Resultado ∈ [1, faces]

O sistema é "Provably Fair" porque:
    1. O Server Seed é mantido SECRETO durante o uso, mas seu hash SHA-256
       é exposto publicamente — o servidor não pode trocar o seed sem ser
       detectado.
    2. O Client Seed é público e pode ser definido pelo usuário.
    3. O Nonce incrementa em +1 a cada rolagem — cada rolagem produz um
       resultado único.
    4. Após a rotação do seed (comando /rotate_seed), o Server Seed antigo
       é revelado em texto puro. QUALQUER PESSOA pode verificar se as
       rolagens anteriores foram honestas recomputando o HMAC.
"""

import hmac
import hashlib


# ---------------------------------------------------------------------------
# Configurações do algoritmo de Amostragem por Rejeição
# ---------------------------------------------------------------------------
# Usamos fatias de 4 bytes (32 bits) do hash. Cada fatia gera um inteiro
# entre 0 e 2^32 - 1. A Amostragem por Rejeição descarta valores que
# cairiam em um intervalo incompleto, garantindo distribuição PERFEITAMENTE
# uniforme.

BYTES_PER_CHUNK = 4          # 4 bytes = 32 bits por tentativa
HEX_CHARS_PER_CHUNK = BYTES_PER_CHUNK * 2  # 8 caracteres hexadecimais
MAX_CHUNK_VALUE = 2 ** 32   # 4294967296 — valor máximo de 4 bytes
MAX_REJECTION_CHUNKS = 8    # Tentamos até 8 fatias do mesmo hash
MAX_COUNTER_EXTENSION = 100 # Fallback: extensão com contador


def compute_hmac(server_seed: str, client_seed: str, nonce: int) -> str:
    """
    Calcula HMAC-SHA256(key, message).

    Fórmula: HMAC-SHA256(server_seed, f"{client_seed}:{nonce}")

    Args:
        server_seed: Seed secreta do servidor (string hexadecimal de 64 chars)
        client_seed: Seed pública do cliente (string definida pelo usuário)
        nonce:       Contador incremental (0, 1, 2, 3, ...)

    Returns:
        Digest hexadecimal de 64 caracteres (32 bytes)
    """
    message = f"{client_seed}:{nonce}".encode("utf-8")
    key = server_seed.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _rejection_sample(hex_digest: str, faces: int) -> int | None:
    """
    Tenta extrair um valor justo do hash usando Amostragem por Rejeição.

    O algoritmo pega fatias de 4 bytes do hash, converte para inteiro, e
    só aceita o valor se ele estiver dentro do maior múltiplo exato de
    'faces' dentro do range de 32 bits. Isso elimina o Modulo Bias.

    Exemplo para d20:
        - 2^32 = 4294967296
        - Maior múltiplo de 20: (4294967296 // 20) * 20 = 4294967280
        - Se value < 4294967280 → aceito, retorna (value % 20) + 1
        - Se value >= 4294967280 → rejeitado, tenta próxima fatia
        - Probabilidade de rejeição: 16/4294967296 ≈ 0.00000037%

    Por que isso importa?
        - Modulo simples: (valor % 20) + 1 favorece os valores 1-16
          porque 2^32 não é divisível por 20. O bias é pequeno, mas REAL.
        - Rejection Sampling: descarta o excesso. Distribuição PERFEITA.

    Args:
        hex_digest: Hash hexadecimal de 64 chars
        faces:      Número de faces do dado (4, 6, 8, 10, 12, 20, etc.)

    Returns:
        Inteiro em [1, faces] se uma fatia for aceita, ou None se todas
        as fatias forem rejeitadas.
    """
    # Limiar de rejeição: o maior valor de 32 bits que é múltiplo exato de faces
    max_valid = (MAX_CHUNK_VALUE // faces) * faces

    for i in range(MAX_REJECTION_CHUNKS):
        start = i * HEX_CHARS_PER_CHUNK
        chunk = hex_digest[start:start + HEX_CHARS_PER_CHUNK]

        # Se não há bytes suficientes, parou
        if len(chunk) < HEX_CHARS_PER_CHUNK:
            break

        # Converte a fatia hex para inteiro
        value = int(chunk, 16)

        # Rejection Sampling: só aceita se estiver DENTRO do range justo
        if value < max_valid:
            return (value % faces) + 1

    # Todas as fatias foram rejeitadas (probabilidade astronomicamente baixa)
    return None


def _counter_extension(
    server_seed: str,
    client_seed: str,
    nonce: int,
    faces: int,
) -> int:
    """
    Fallback extremamente raro: estende o cálculo com um contador interno.

    Se TODAS as 8 fatias do hash principal forem rejeitadas, este método
    calcula HMACs adicionais com um contador: ClientSeed:Nonce:Counter.

    A probabilidade de chegar aqui é tão baixa que é virtualmente impossível
    na prática, mas a implementação é completa para garantir correção
    matemática absoluta.

    Args:
        server_seed: Seed secreta do servidor
        client_seed: Seed pública do cliente
        nonce:       Nonce atual
        faces:       Número de faces do dado

    Returns:
        Inteiro em [1, faces]
    """
    max_valid = (MAX_CHUNK_VALUE // faces) * faces

    for counter in range(1, MAX_COUNTER_EXTENSION + 1):
        extended_message = f"{client_seed}:{nonce}:{counter}".encode("utf-8")
        extended_hmac = hmac.new(
            server_seed.encode("utf-8"),
            extended_message,
            hashlib.sha256,
        ).hexdigest()

        first_chunk = extended_hmac[:HEX_CHARS_PER_CHUNK]
        value = int(first_chunk, 16)

        if value < max_valid:
            return (value % faces) + 1

    # Último recurso absoluto: modulo puro (NUNCA deve acontecer)
    # Matematicamente, a probabilidade é ~(16/2^32)^108 ≈ 0
    last_resort = int(extended_hmac[:HEX_CHARS_PER_CHUNK], 16)
    return (last_resort % faces) + 1


def generate_roll(
    server_seed: str,
    client_seed: str,
    nonce: int,
    faces: int,
) -> int:
    """
    Gera UMA rolagem de dado provably fair.

    Pipeline completo:
        1. Computa HMAC-SHA256(server_seed, client_seed:nonce)
        2. Tenta Amostragem por Rejeição nas fatias de 4 bytes do hash
        3. Se todas falharem, usa extensão por contador
        4. Retorna valor em [1, faces]

    Args:
        server_seed: Seed secreta do servidor (hex string, 64 chars)
        client_seed: Seed pública do cliente
        nonce:       Número inteiro que incrementa a cada rolagem
        faces:       Quantas faces o dado tem (ex: 20 para d20)

    Returns:
        Inteiro entre 1 e faces (inclusive), com distribuição PERFEITAMENTE
        uniforme — sem nenhum viés de módulo.

    Exemplo:
        >>> generate_roll(
        ...     server_seed="a1b2...",
        ...     client_seed="minha_seed_personalizada",
        ...     nonce=42,
        ...     faces=20,
        ... )
        15  # Valor entre 1 e 20
    """
    # Passo 1: Computa o HMAC (entropia bruta)
    hmac_digest = compute_hmac(server_seed, client_seed, nonce)

    # Passo 2: Tenta Rejection Sampling no hash principal
    result = _rejection_sample(hmac_digest, faces)
    if result is not None:
        return result

    # Passo 3: Fallback — extensão por contador
    return _counter_extension(server_seed, client_seed, nonce, faces)


def verify_roll(
    server_seed: str,
    client_seed: str,
    nonce: int,
    faces: int,
    result: int,
) -> bool:
    """
    Verifica se uma rolagem foi gerada de forma justa.

    Esta é a função de VERIFICAÇÃO PÚBLICA. Depois que o servidor revela
    o Server Seed (via /rotate_seed), QUALQUER PESSOA pode chamar esta
    função com os parâmetros da rolagem e confirmar que o resultado é
    legítimo.

    Args:
        server_seed: O seed do servidor REVELADO (texto plano)
        client_seed: O client seed usado na rolagem
        nonce:       O nonce da rolagem (mostrado no footer do embed)
        faces:       Quantas faces o dado tem
        result:      O resultado que se quer verificar

    Returns:
        True se o resultado for consistente com o cálculo provably fair.

    Exemplo de uso:
        >>> verify_roll(
        ...     server_seed="a1b2c3...",  # Revelado pelo /rotate_seed
        ...     client_seed="minha_seed",
        ...     nonce=42,
        ...     faces=20,
        ...     result=15,
        ... )
        True  # Rolagem verificada como honesta!
    """
    expected = generate_roll(server_seed, client_seed, nonce, faces)
    return expected == result