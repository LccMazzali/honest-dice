"""
parser.py
=============================================================================
ANALISADOR DE EXPRESSÕES DE DADOS

Tokeniza a expressão em grupos de dados e modificadores planos.

Exemplos:
    "1d20+5"      → 1d20, modificador +5
    "4d6"         → 4d6, soma
    "2d20kh1"     → 2d20, keep highest 1 (vantagem)
    "2d20kl1"     → 2d20, keep lowest 1 (desvantagem)
    "2d6+1d4+3"   → 2d6 + 1d4, modificador +3
    "2d6+1d4-3"   → 2d6 + 1d4, modificador -3
"""

import re
from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class DiceComponent:
    """
    Representa UM grupo de dados na expressão.

    Attributes:
        count:      Quantidade de dados
        faces:      Número de faces
        modifier:   Modificador plano (+5, -3, etc.)
        keep_mode:  None, 'kh' (keep highest), 'kl' (keep lowest)
        keep_count: Quantos dados manter (kh/kl)
        sign:       1 (positivo) ou -1 (negativo) — ex: em "2d6-1d4", o 1d4 tem sign=-1
    """
    count: int
    faces: int
    modifier: int = 0
    keep_mode: Optional[str] = None
    keep_count: int = 1
    sign: int = 1


class DiceExpression:
    """Expressão de dados completa."""

    def __init__(self, components: List[DiceComponent], flat_modifier: int = 0,
                 flat_modifier_parts: Optional[List[int]] = None):
        self.components = components
        self.flat_modifier = flat_modifier
        self.flat_modifier_parts = flat_modifier_parts or []

    @property
    def total_count(self) -> int:
        return sum(c.count for c in self.components)

    @property
    def is_valid(self) -> bool:
        return len(self.components) > 0


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Token: opcional sinal (+/-), depois um grupo de dados ou um número
#   Grupo 1 (opcional): sinal +/-
#   Grupo 2: o resto (dados ou número)
TOKEN_PATTERN = re.compile(
    r"([+-])?(?:\d*d\d+(?:kh\d+|kl\d+)?|\d+)",
    re.IGNORECASE,
)

# Detecta se um token é um grupo de dados (contém "d")
DICE_PATTERN = re.compile(
    r"(\d+)?d(\d+)(?:kh(\d+)|kl(\d+))?",
    re.IGNORECASE,
)

VALID_FACES: set[int] = {4, 6, 8, 10, 12, 20, 100}
MAX_DICE_PER_GROUP = 100
MAX_EXPRESSION_LENGTH = 60


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def parse_expression(expression: str) -> Optional[DiceExpression]:
    """
    Analisa uma string de expressão de dados.

    Tokeniza a expressão em partes separadas por +/-, processa cada
    token como grupo de dados ou modificador plano.

    Exemplos:
        "1d20+5"      → 1d20, flat_modifier=+5
        "2d6+1d4+3"   → 2d6 + 1d4, flat_modifier=+3  (CORRETO!)
        "2d6-1d4+3"   → 2d6 + (-1)d4, flat_modifier=+3
    """
    if not expression or not isinstance(expression, str):
        return None

    expression = expression.strip().replace(" ", "")
    if len(expression) > MAX_EXPRESSION_LENGTH or len(expression) < 2:
        return None

    # Tokeniza: "2d6+1d4+3" → ['2d6', '+1d4', '+3']
    tokens = TOKEN_PATTERN.findall(expression)
    # findall retorna grupos de captura. Como temos um grupo opcional
    # ([+-])? e o resto, precisamos juntar pares consecutivos.
    # Na verdade, findall com um grupo de captura retorna SÓ o grupo.
    # Vamos usar finditer.

    tokens = []
    for match in TOKEN_PATTERN.finditer(expression):
        sign = match.group(1) or ""
        body = match.group(0)
        if not sign and body and body[0] in "+-":
            # O match pode já incluir o sinal no body
            pass
        tokens.append(sign + body.lstrip("+-") if sign else body)

    # Se não encontrou nada, tenta interpretar como número puro
    if not tokens:
        return None

    components: List[DiceComponent] = []
    flat_modifier = 0
    flat_modifier_parts: List[int] = []

    for token in tokens:
        # Separa sinal opcional do resto
        token_sign = ""
        clean_token = token
        if token and token[0] in "+-":
            token_sign = token[0]
            clean_token = token[1:]

        dice_match = DICE_PATTERN.match(clean_token)

        if dice_match:
            # É um grupo de dados
            count_str = dice_match.group(1)
            faces_str = dice_match.group(2)
            kh_str = dice_match.group(3)
            kl_str = dice_match.group(4)

            count = int(count_str) if count_str else 1
            faces = int(faces_str)

            if faces not in VALID_FACES:
                return None
            if count < 1 or count > MAX_DICE_PER_GROUP:
                return None

            # Keep mode
            keep_mode = None
            keep_count = 1
            if kh_str:
                keep_mode = "kh"
                keep_count = int(kh_str) if kh_str else 1
            elif kl_str:
                keep_mode = "kl"
                keep_count = int(kl_str) if kl_str else 1
            if keep_count < 1 or keep_count > count:
                keep_count = count

            components.append(DiceComponent(
                count=count, faces=faces,
                keep_mode=keep_mode,
                keep_count=keep_count,
                sign=1 if token_sign != "-" else -1,
            ))

        else:
            # É um modificador plano (ex: +5, -3, +4, +3)
            try:
                val = int(token)
                flat_modifier += val
                flat_modifier_parts.append(val)
            except ValueError:
                return None

    if not components:
        return None

    return DiceExpression(components, flat_modifier, flat_modifier_parts)


def describe_valid_dice() -> str:
    return ", ".join(f"d{f}" for f in sorted(VALID_FACES))