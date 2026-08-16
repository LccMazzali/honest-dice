"""
commands.py
=============================================================================
COMANDOS DE BARRA (SLASH COMMANDS) — Interface do bot no Discord

Este módulo implementa os comandos de barra do Honest Dice usando a API
de Interactions do discord.py (app_commands).

COMANDOS DISPONÍVEIS:
    /roll <expression> [secret]
        Comando principal. Roda dados com o sistema Provably Fair.
        Exemplo: /roll 1d20+5

    /r <expression> [secret]
        Atalho para /roll.

    /history [user]
        Exibe o histórico de rolagens. Sem argumentos, mostra seu próprio
        histórico. Administradores podem usar user para ver o histórico
        de outro usuário, ou "all" para ver o histórico completo.

    /rotate_seed
        Rotaciona o Server Seed. Revela o seed anterior publicamente.
        Restrito a administradores.

    /status
        Exibe o estado atual do sistema Provably Fair.

    /set_seed <seed>
        Permite que o usuário defina um Client Seed personalizado.

    /verify <server_seed> <client_seed> <nonce> <faces> <result>
        Verifica se uma rolagem foi gerada de forma justa.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from dice.parser import parse_expression, describe_valid_dice, VALID_FACES
from dice.roller import roll_expression
from dice import history
from bot.embeds import (
    format_roll_embed,
    format_rotation_embed,
    format_status_embed,
    format_verify_embed,
    format_history_embed,
)
from crypto.state import (
    rotate_seed,
    get_state,
    set_client_seed,
    generate_client_seed,
)
from crypto.provably_fair import verify_roll, generate_roll
from crypto.state import get_server_seed, get_client_seed, get_nonce

import logging
log = logging.getLogger("honest_dice")


# ---------------------------------------------------------------------------
# Valores críticos do chi-quadrado para alpha=0.05
# ---------------------------------------------------------------------------

CHI2_CRITICAL = {
    4: 7.815,
    6: 11.070,
    8: 14.067,
    10: 16.919,
    12: 19.675,
    20: 30.144,
    100: 123.225,
}


# ---------------------------------------------------------------------------
# Cog de comandos
# ---------------------------------------------------------------------------

class HonestDiceCommands(commands.Cog):
    """
    Cog contendo todos os comandos de barra do Honest Dice.

    Cog é a forma como discord.py organiza grupos de comandos. Esta classe
    é registrada no bot em setup_hook().
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------------------------------------------------
    # Utilitários de autorização
    # -----------------------------------------------------------------------

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """
        Verifica se o usuário tem permissões de administrador no servidor.

        Args:
            interaction: A interação do Discord

        Returns:
            True se o usuário for administrador
        """
        if interaction.guild is None:
            return False
        return interaction.user.guild_permissions.administrator

    # -----------------------------------------------------------------------
    # /roll — Comando principal para rolar dados
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="roll",
        description="Rola dados com RNG Provably Fair. Ex: 1d20+5, 4d6, 2d8-3",
    )
    @app_commands.describe(
        expression="Expressão de dados (ex: 1d20+5, 4d6, 2d8-3)",
        secret="Se True, apenas você vê o resultado (padrão: False)",
    )
    async def roll(
        self,
        interaction: discord.Interaction,
        expression: str,
        secret: bool = False,
    ):
        """
        Comando /roll — Roda dados usando o sistema Provably Fair.

        Fluxo:
            1. Parseia a expressão (ex: "1d20+5" → 1 dado de 20 faces + modificador +5)
            2. Se inválida, retorna erro com dados suportados
            3. Se válida, executa a rolagem via roller.py
            4. Registra a rolagem no histórico do servidor
            5. Formata o resultado como Rich Embed (com ID do histórico)
            6. Envia (ephemeral se secret=True)

        Args:
            expression: String como "1d20+5", "4d6", "d20"
            secret:     Se True, envia como mensagem efêmera
        """
        # --- Passo 1: Parse ---
        parsed = parse_expression(expression)

        if parsed is None:
            # Expressão inválida — mostra erro com formato correto
            valid_dice = describe_valid_dice()
            embed = discord.Embed(
                title="❌ Expressão Inválida",
                description=(
                    f"Não foi possível interpretar `{expression}`.\n\n"
                    f"**Exemplos válidos:**\n"
                    f"`1d20` — dado simples\n"
                    f"`1d20+5` — com modificador\n"
                    f"`4d6` — múltiplos dados\n"
                    f"`2d20kh1` — vantagem (keep highest)\n"
                    f"`2d20kl1` — desvantagem (keep lowest)\n"
                    f"`2d6+1d4+3` — grupos diferentes + modificador\n\n"
                    f"**Dados:** {describe_valid_dice()}"
                ),
                color=0xFF0000,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # --- Passo 2: Rolar ---
        result = roll_expression(expression, parsed)

        if result is None:
            await interaction.response.send_message(
                "❌ Erro interno ao processar a rolagem.",
                ephemeral=True,
            )
            return

        # --- Passo 3: Registrar no histórico (apenas se for em servidor) ---
        history_id = None
        if interaction.guild is not None:
            history_id = history.add_entry(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                user_name=str(interaction.user),
                result=result,
            )

        # --- Passo 4: Formatar e enviar ---
        embed = format_roll_embed(
            result,
            ephemeral=secret,
            history_id=history_id,
        )

        # Se for secreto, envia apenas para o usuário
        await interaction.response.send_message(embed=embed, ephemeral=secret)

    # -----------------------------------------------------------------------
    # /r — Atalho para /roll
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="r",
        description="Atalho para /roll. Ex: /r 1d20+5",
    )
    @app_commands.describe(
        expression="Expressão de dados (ex: 1d20+5, 4d6, 2d8-3)",
        secret="Se True, apenas você vê o resultado (padrão: False)",
    )
    async def roll_short(
        self,
        interaction: discord.Interaction,
        expression: str,
        secret: bool = False,
    ):
        """Atalho para /roll — delega para o handler do /roll."""
        await self.roll.callback(self, interaction, expression, secret)

    # -----------------------------------------------------------------------
    # /history — Histórico de rolagens
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="history",
        description="Exibe seu histórico de rolagens. Admin pode ver o histórico completo.",
    )
    @app_commands.describe(
        user="[Admin] 'all' para ver tudo, ou @usuário para ver de alguém",
    )
    async def history_cmd(
        self,
        interaction: discord.Interaction,
        user: Optional[str] = None,
    ):
        """
        Comando /history — Consulta o histórico de rolagens.

        Modos de operação:
            1. Sem argumentos: mostra as últimas 25 rolagens do próprio usuário
            2. Admin com user="all": mostra as últimas 50 rolagens do servidor
            3. Admin com user="@usuário": mostra as últimas 25 de um usuário específico

        Args:
            user: String opcional. "all" para histórico completo, ou
                  nome/ID de usuário para filtrar (admin apenas).
        """
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ Este comando só funciona em servidores.",
                ephemeral=True,
            )
            return

        is_admin = self._is_admin(interaction)

        # --- Modo 1: Admin com "all" → histórico completo do servidor ---
        if user and user.lower() == "all":
            if not is_admin:
                await interaction.response.send_message(
                    "❌ Apenas administradores podem ver o histórico completo do servidor.",
                    ephemeral=True,
                )
                return

            entries = history.get_guild_history(guild.id)
            embed = format_history_embed(entries, is_admin=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # --- Modo 2: Admin especificou um usuário → histórico dele ---
        if user and is_admin:
            # Tenta extrair o user_id de uma menção (<@123456>)
            target_id = None
            if user.startswith("<@") and user.endswith(">"):
                target_id = int(user.strip("<@!>"))
            elif user.isdigit():
                target_id = int(user)
            else:
                # Tenta buscar por nome no servidor
                members = guild.members
                for member in members:
                    if user.lower() in member.name.lower() or \
                       user.lower() in member.display_name.lower():
                        target_id = member.id
                        break

            if target_id is not None:
                entries = history.get_user_history(guild.id, target_id)
                embed = format_history_embed(entries, is_admin=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            else:
                await interaction.response.send_message(
                    f"❌ Usuário `{user}` não encontrado. Use menção (@usuário), "
                    "ID numérico, ou 'all' para tudo.",
                    ephemeral=True,
                )
                return

        # --- Modo 3: Não-admin com argumento → erro ---
        if user and not is_admin:
            await interaction.response.send_message(
                "❌ Apenas administradores podem consultar o histórico de outros usuários.",
                ephemeral=True,
            )
            return

        # --- Modo 4: Padrão → histórico do próprio usuário ---
        entries = history.get_user_history(guild.id, interaction.user.id)
        embed = format_history_embed(entries, is_admin=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -----------------------------------------------------------------------
    # /rotate_seed — Rotaciona o Server Seed (Admin)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="rotate_seed",
        description="[Admin] Rotaciona o Server Seed. Revela o seed anterior publicamente.",
    )
    @app_commands.default_permissions(administrator=True)
    async def rotate_seed_cmd(self, interaction: discord.Interaction):
        """
        Comando /rotate_seed — Rotaciona o Server Seed.

        Restrito a administradores do servidor.
        Efeitos:
            1. Server Seed atual → revelado em texto puro
            2. Novo Server Seed gerado (32 bytes criptográficos)
            3. Nonce resetado para 0
            4. Embed de confirmação com seed anterior e novo hash
        """
        rotation = rotate_seed()

        embed = format_rotation_embed(
            previous_seed=rotation["previous_seed"],
            new_hash=rotation["new_hash"],
        )

        await interaction.response.send_message(embed=embed)

    # -----------------------------------------------------------------------
    # /status — Estado do sistema Provably Fair
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="status",
        description="Exibe o estado atual do sistema Provably Fair.",
    )
    async def status(self, interaction: discord.Interaction):
        """
        Comando /status — Mostra informações públicas do estado.

        Exibe:
            - SHA-256 do Server Seed atual
            - Client Seed em uso
            - Nonce atual
            - Total de rolagens
            - Último seed revelado (se houver)
        """
        state = get_state()
        embed = format_status_embed(state)
        await interaction.response.send_message(embed=embed)

    # -----------------------------------------------------------------------
    # /set_seed — Define Client Seed personalizado
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="set_seed",
        description="Define um Client Seed personalizado para suas rolagens.",
    )
    @app_commands.describe(
        seed="Sua string de Client Seed personalizada (mín. 4, máx. 64 caracteres)",
    )
    async def set_seed(self, interaction: discord.Interaction, seed: str):
        """
        Comando /set_seed — Permite ao usuário controlar o Client Seed.

        O Client Seed é parte da entropia do sistema Provably Fair:
            HMAC-SHA256(ServerSeed, "ClientSeed:Nonce")

        Ao controlar o Client Seed, o usuário tem garantia adicional de
        que o servidor não pode prever os resultados (já que o servidor
        não controla o Client Seed).

        Args:
            seed: String personalizada (4-64 caracteres)
        """
        # Validação de tamanho
        if len(seed) < 4:
            await interaction.response.send_message(
                "❌ O Client Seed deve ter no mínimo 4 caracteres.",
                ephemeral=True,
            )
            return

        if len(seed) > 64:
            await interaction.response.send_message(
                "❌ O Client Seed deve ter no máximo 64 caracteres.",
                ephemeral=True,
            )
            return

        # Aplica o novo seed
        set_client_seed(seed)

        embed = discord.Embed(
            title="✅ Client Seed Atualizado",
            description=(
                f"Novo Client Seed: `{seed}`\n\n"
                "O nonce foi resetado para 0 com este novo seed.\n"
                "Agora você pode verificar que o servidor não pode "
                "prever os resultados."
            ),
            color=0x00FF00,
        )

        embed.set_footer(text="Honest Dice — Provably Fair | Transparência Total")
        await interaction.response.send_message(embed=embed)

    # -----------------------------------------------------------------------
    # /verify — Verifica rolagem pelo Provably Fair
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="verify",
        description="Verifica se uma rolagem foi gerada de forma justa.",
    )
    @app_commands.describe(
        server_seed="Server Seed revelado (do /rotate_seed)",
        client_seed="Client Seed usado na rolagem",
        nonce="Nonce exibido no footer da rolagem",
        faces="Número de faces do dado (4, 6, 8, 10, 12, 20, 100)",
        result="Resultado que você quer verificar",
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        server_seed: str,
        client_seed: str,
        nonce: int,
        faces: int,
        result: int,
    ):
        """
        Comando /verify — Verificação pública de uma rolagem.

        QUALQUER PESSOA pode usar este comando para verificar se uma
        rolagem foi honesta, desde que tenha:
            - O Server Seed revelado (do /rotate_seed)
            - O Client Seed da época
            - O Nonce (mostrado no footer de cada rolagem)

        Args:
            server_seed: Server Seed em texto puro (revelado pelo /rotate_seed)
            client_seed: Client Seed usado na rolagem
            nonce:       Nonce da rolagem (inteiro)
            faces:       Número de faces (4, 6, 8, 10, 12, 20, 100)
            result:      Resultado a verificar (1-faces)
        """
        # Valida faces
        if faces not in VALID_FACES:
            valid = describe_valid_dice()
            await interaction.response.send_message(
                f"❌ Dado inválido. Faces válidas: {valid}",
                ephemeral=True,
            )
            return

        # Executa verificação
        is_valid = verify_roll(server_seed, client_seed, nonce, faces, result)

        # Formata embeds diferentes para valid/invalid
        embed = format_verify_embed(
            is_valid=is_valid,
            server_seed=server_seed,
            client_seed=client_seed,
            nonce=nonce,
            faces=faces,
            result=result,
        )

        await interaction.response.send_message(embed=embed)

    # -----------------------------------------------------------------------
    # /test_fairness — Teste estatístico de chi-quadrado
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="test_fairness",
        description="[Admin] Roda 10.000 rolagens e testa a uniformidade do RNG.",
    )
    @app_commands.describe(
        faces="Número de faces do dado para testar (padrão: 20)",
        rolls="Quantidade de rolagens (padrão: 10000, máx: 50000)",
    )
    @app_commands.default_permissions(administrator=True)
    async def test_fairness(
        self,
        interaction: discord.Interaction,
        faces: int = 20,
        rolls: int = 10000,
    ):
        """
        Executa N rolagens de um dado e aplica o teste de chi-quadrado
        para verificar se a distribuição é uniforme.

        O teste de chi-quadrado compara a frequência observada de cada
        face com a frequência esperada (N/faces). Se o valor de chi²
        for menor que o valor crítico (para alpha=0.05), o RNG passou
        no teste — não há evidência de viés.

        Args:
            faces: Número de faces (4, 6, 8, 10, 12, 20, 100)
            rolls: Quantidade de rolagens (1000-50000)
        """
        # Valida faces
        if faces not in VALID_FACES:
            await interaction.response.send_message(
                f"❌ Dado inválido. Faces: {describe_valid_dice()}",
                ephemeral=True,
            )
            return

        # Valida quantidade
        rolls = max(1000, min(rolls, 50000))

        # Avisa que vai demorar
        await interaction.response.defer(ephemeral=False)

        log.info(
            "Teste de fairness: %d rolagens de d%d por %s",
            rolls, faces, interaction.user,
        )

        # Roda as rolagens
        server_seed = get_server_seed()
        client_seed = get_client_seed()
        start_nonce = get_nonce()

        counts = [0] * (faces + 1)  # 1-indexed

        for i in range(rolls):
            value = generate_roll(
                server_seed=server_seed,
                client_seed=client_seed,
                nonce=start_nonce + i,
                faces=faces,
            )
            counts[value] += 1

        # Calcula chi-quadrado
        expected = rolls / faces
        chi2 = sum(
            (obs - expected) ** 2 / expected
            for obs in counts[1:]
        )

        critical = CHI2_CRITICAL.get(faces, 30.144)
        df = faces - 1
        passed = chi2 < critical

        # Monta o embed
        embed = discord.Embed(
            title="🔬 Teste de Fairness — Chi²",
            description=(
                f"**{rolls:,}** rolagens de **d{faces}**\n"
                f"Nonces: `{start_nonce}` a `{start_nonce + rolls - 1}`"
            ),
            color=0x00FF00 if passed else 0xFF0000,
        )

        # Tabela de frequências (compacta)
        freq_lines = []
        for face in range(1, faces + 1):
            bar = "█" * int(counts[face] / max(1, rolls // 40))
            freq_lines.append(f"`{face:3d}` {counts[face]:5d} {bar}")

        # Mostra em blocos para não estourar o limite do embed
        chunk_size = 20
        for chunk_start in range(0, len(freq_lines), chunk_size):
            chunk = freq_lines[chunk_start:chunk_start + chunk_size]
            embed.add_field(
                name=f"Faces {chunk_start+1}–{min(chunk_start+chunk_size, faces)}",
                value="```\n" + "\n".join(chunk) + "\n```",
                inline=False,
            )

        embed.add_field(
            name="📊 Resultado",
            value=(
                f"**χ² = {chi2:.4f}**\n"
                f"**df = {df}**\n"
                f"**Valor crítico (α=0.05) = {critical}**\n"
                f"**Esperado por face = {expected:.1f}**"
            ),
            inline=False,
        )

        if passed:
            embed.add_field(
                name="✅ RNG APROVADO",
                value=(
                    f"χ² ({chi2:.4f}) < valor crítico ({critical}).\n"
                    "Não há evidência de viés estatístico. "
                    "O gerador Provably Fair é uniforme."
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="⚠️ RNG NÃO PASSOU",
                value=(
                    f"χ² ({chi2:.4f}) >= valor crítico ({critical}).\n"
                    "Pode haver viés. Verifique se o Server Seed não "
                    "foi rotacionado durante o teste."
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"Honest Dice — Provably Fair | {rolls:,} rolagens"
        )

        log.info(
            "Teste de fairness: χ²=%.4f, crítico=%.4f, %s",
            chi2, critical, "APROVADO" if passed else "REPROVADO",
        )

        await interaction.followup.send(embed=embed)


    # -----------------------------------------------------------------------
    # /consistency — Teste de consistência determinística
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="consistency",
        description="Demo: mesma expressão 3x com mesmos seeds → mesmo resultado.",
    )
    async def consistency(self, interaction: discord.Interaction):
        from crypto.provably_fair import generate_roll

        demo_server = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        demo_client = "demo_seed_consistente"
        demo_nonce = 42

        r1 = generate_roll(demo_server, demo_client, demo_nonce, 20)
        r2 = generate_roll(demo_server, demo_client, demo_nonce, 20)
        r3 = generate_roll(demo_server, demo_client, demo_nonce, 20)

        resultados = f"{r1}, {r2}, {r3}"
        iguais = r1 == r2 == r3

        embed = discord.Embed(
            title="🔬 Teste de Consistência",
            description=(
                f"`1d20` rolado **3 vezes** com:\n"
                f"• Server Seed: `{demo_server[:16]}..`\n"
                f"• Client Seed: `{demo_client}`\n"
                f"• Nonce: `{demo_nonce}`\n\n"
                f"Resultados: **{resultados}**\n"
                f"→ {'✅ IDÊNTICOS' if iguais else '❌ DIFERENTES'}"
            ),
            color=0x00FF00 if iguais else 0xFF0000,
        )

        if iguais:
            embed.add_field(
                name="🧮 Por quê?",
                value=(
                    "HMAC-SHA256 é **determinístico**: mesmos inputs\n"
                    "(key + message) produzem exatamente o mesmo hash.\n"
                    "Após Rejection Sampling, o resultado é idêntico.\n\n"
                    "Qualquer pessoa pode verificar qualquer rolagem\n"
                    "depois que o Server Seed for revelado."
                ),
                inline=False,
            )

        embed.set_footer(text="Honest Dice — Provably Fair | HMAC-SHA256")
        await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Função de configuração
# ---------------------------------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    """
    Função de setup exigida pelo discord.py para carregar Cogs via
    bot.load_extension().

    Args:
        bot: Instância do bot onde o Cog será registrado
    """
    await bot.add_cog(HonestDiceCommands(bot))