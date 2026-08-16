"""
main.py
=============================================================================
PONTO DE ENTRADA — Honest Dice Bot
"""

VERSION = "2.0.0"
"""Versao atual do Honest Dice Bot."""

import logging
import os
import sys
import discord
from discord.ext import commands

from crypto.state import load_state, get_state
from bot.commands import HonestDiceCommands

# ---------------------------------------------------------------------------
# Logging estruturado
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "honest_dice.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)

log = logging.getLogger("honest_dice")

# ---------------------------------------------------------------------------
# Configuração do Token
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not BOT_TOKEN:
    log.error("Token do Discord não encontrado!")
    log.error("Defina a variável de ambiente DISCORD_BOT_TOKEN")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Classe do Bot
# ---------------------------------------------------------------------------

class HonestDiceBot(commands.Bot):
    """Bot Honest Dice com logging estruturado."""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Honest Dice v{VERSION} — Provably Fair Dice Rolling for RPG",
        )
        self.start_time = None

    async def setup_hook(self):
        """Carrega estado, registra comandos e sincroniza."""
        load_state()
        await self.add_cog(HonestDiceCommands(self))
        await self.tree.sync()

        state = get_state()
        log.info("Honest Dice v%s inicializado", VERSION)
        log.info("Server Seed Hash: %s...", state["server_seed_hash"][:16])
        log.info("Client Seed: %s...", state["client_seed"][:16])
        log.info("Nonce: %d", state["nonce"])
        log.info("Total de rolagens: %d", state["rolls"])
        log.info("Comandos registrados: %d", len(self.tree.get_commands()))

    async def on_ready(self):
        """Loga quando o bot conecta ao Discord."""
        import time
        self.start_time = time.time()

        log.info("Bot conectado como: %s (ID: %d)", self.user, self.user.id)
        log.info("Servidores: %d", len(self.guilds))
        log.info(
            "Convite: https://discord.com/api/oauth2/authorize"
            "?client_id=%d&scope=bot+applications.commands",
            self.user.id,
        )


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Iniciando Honest Dice...")
    bot = HonestDiceBot()
    bot.run(BOT_TOKEN, log_handler=None)