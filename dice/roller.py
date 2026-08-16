"""
roller.py
=============================================================================
EXECUTOR DE ROLAGENS — Conecta o parser ao RNG criptográfico

Suporta rolagem normal e vantagem/desvantagem (keep highest / keep lowest).
"""

from dataclasses import dataclass, field
from typing import List, Optional

from crypto.provably_fair import generate_roll, verify_roll
from crypto.state import (
    get_server_seed,
    get_client_seed,
    get_nonce,
    increment_nonce,
    get_state as get_crypto_state,
)
from dice.parser import DiceExpression, DiceComponent


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class IndividualRoll:
    """
    Representa o resultado de UM ÚNICO dado.

    Attributes:
        faces:               Número de faces
        value:               Valor rolado (1..faces)
        is_critical_fail:    True se value == 1
        is_critical_success: True se value == faces
        kept:                True se o dado foi mantido (kh/kl)
                             False se foi descartado
    """
    faces: int
    value: int
    is_critical_fail: bool = False
    is_critical_success: bool = False
    kept: bool = True


@dataclass
class RollGroup:
    """
    Representa um GRUPO de dados idênticos.

    Attributes:
        count:          Quantidade de dados rolados (total, incluindo descartados)
        faces:          Número de faces
        modifier:       Modificador plano
        rolls:          Lista de resultados individuais (todos)
        kept_count:     Quantos dados foram mantidos (kh/kl)
        kept_rolls:     Lista apenas dos dados mantidos
        total:          Soma dos valores MANTIDOS
        modifier_total: total + modifier
    """
    count: int
    faces: int
    modifier: int = 0
    rolls: List[IndividualRoll] = field(default_factory=list)
    kept_count: int = 0
    kept_rolls: List[IndividualRoll] = field(default_factory=list)
    total: int = 0
    modifier_total: int = 0


@dataclass
class RollResult:
    """
    Representa o resultado COMPLETO de uma expressão.

    Attributes:
        groups:           Lista de grupos rolados
        grand_total:      Soma de todos os modifier_totals
        nonce:            Nonce do primeiro dado rolado
        client_seed:      Client seed usado
        server_seed_hash: SHA-256 do server seed
        expression:       Expressão original
    """
    groups: List[RollGroup] = field(default_factory=list)
    grand_total: int = 0
    nonce: int = 0
    client_seed: str = ""
    server_seed_hash: str = ""
    expression: str = ""
    flat_modifier: int = 0
    flat_modifier_parts: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def roll_expression(expression: str, parsed: DiceExpression) -> Optional[RollResult]:
    """
    Executa uma expressão de dados usando o RNG Provably Fair.

    Suporta keep highest (khN) e keep lowest (klN):
        - Rola todos os dados do grupo
        - Ordena por valor
        - Mantém apenas os N maiores (kh) ou menores (kl)
        - Os descartados ficam marcados kept=False no histórico
    """
    server_seed = get_server_seed()
    client_seed = get_client_seed()
    state = get_crypto_state()

    result = RollResult(
        expression=expression,
        client_seed=client_seed,
        server_seed_hash=state["server_seed_hash"],
        flat_modifier=parsed.flat_modifier,
        flat_modifier_parts=parsed.flat_modifier_parts,
    )

    first_nonce = None

    for component in parsed.components:
        has_keep = component.keep_mode is not None
        group = RollGroup(
            count=component.count,
            faces=component.faces,
            modifier=0,  # modificadores agora estão em flat_modifier
        )

        all_rolls: List[IndividualRoll] = []

        # Roda todos os dados do grupo
        for _ in range(component.count):
            nonce = get_nonce()
            if first_nonce is None:
                first_nonce = nonce

            value = generate_roll(
                server_seed=server_seed,
                client_seed=client_seed,
                nonce=nonce,
                faces=component.faces,
            )

            increment_nonce()

            roll = IndividualRoll(
                faces=component.faces,
                value=value,
                is_critical_fail=(value == 1),
                is_critical_success=(value == component.faces),
            )
            all_rolls.append(roll)

        # Aplica keep highest / keep lowest
        if has_keep:
            sorted_rolls = sorted(all_rolls, key=lambda r: r.value, reverse=True)

            if component.keep_mode == "kh":
                # Mantém os N maiores
                kept = sorted_rolls[:component.keep_count]
                discarded = sorted_rolls[component.keep_count:]
            else:  # kl
                # Mantém os N menores (inverte a ordem)
                kept = sorted_rolls[-component.keep_count:]
                discarded = sorted_rolls[:-component.keep_count]

            for r in discarded:
                r.kept = False

            # Preserva a ordem original nos rolls (para exibição)
            group.rolls = all_rolls
            group.kept_rolls = kept
            group.kept_count = component.keep_count
            group.total = sum(r.value for r in kept)
        else:
            group.rolls = all_rolls
            group.kept_rolls = all_rolls
            group.kept_count = component.count
            group.total = sum(r.value for r in all_rolls)

        group.modifier_total = group.total + component.modifier
        result.groups.append(group)
        result.grand_total += group.modifier_total * component.sign

    # Adiciona modificadores planos ao total final
    result.grand_total += parsed.flat_modifier

    result.nonce = first_nonce if first_nonce is not None else 0

    # --- VERIFICAÇÃO: recalcula o total a partir dos dados individuais ---
    _verify_total = 0
    for i, g in enumerate(result.groups):
        _verify_total += g.total * parsed.components[i].sign
    _verify_total += parsed.flat_modifier

    if _verify_total != result.grand_total:
        import logging
        logging.getLogger("honest_dice").error(
            "DISCREPANCIA no total: calculado=%d, verificado=%d, expressao=%s",
            result.grand_total, _verify_total, expression,
        )
        result.grand_total = _verify_total  # corrige

    return result


def verify_roll_result(
    server_seed: str,
    client_seed: str,
    start_nonce: int,
    faces: int,
    expected_values: List[int],
) -> bool:
    """Verifica uma sequência de rolagens."""
    for i, expected in enumerate(expected_values):
        nonce = start_nonce + i
        if not verify_roll(server_seed, client_seed, nonce, faces, expected):
            return False
    return True