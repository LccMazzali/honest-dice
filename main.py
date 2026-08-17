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
import asyncio
import discord
from discord.ext import commands

from crypto.state import load_state, get_state
from bot.commands import HonestDiceCommands

# aiohttp: vem junto com discord.py (sem dependencia extra)
try:
    from aiohttp import web
except ImportError:
    web = None

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
# Servidor HTTP de saude (Render Free: Web Service precisa responder HTTP)
# UptimeRobot (gratuito) faz ping a cada 5 min -> o servico nunca dorme.
# URL: /health  ->  {"ok":true}
# ---------------------------------------------------------------------------

async def _health_handler(request):
    return web.json_response({"ok": True, "bot": "honest-dice"})


async def run_http_server(_bot=None):
    """Sobe um mini servidor aiohttp na porta $PORT (3000 default)."""
    if web is None:
        log.warning("aiohttp indisponivel — servidor HTTP de saude desligado")
        return
    app = web.Application()
    app.router.add_get("/", _health_handler)
    app.router.add_get("/health", _health_handler)
    app.router.add_get("/healthz", _health_handler)
    port = int(os.environ.get("PORT", "3000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Servidor HTTP de saude ativo na porta %d (/health)", port)


async def _main():
    """Roda o bot do Discord + servidor HTTP de saude em paralelo."""
    log.info("Iniciando Honest Dice...")
    bot = HonestDiceBot()
    try:
        await run_http_server(bot)
    except Exception as e:  # nunca deixar o bot cair por causa do healthcheck
        log.warning("Servidor de saude falhou (bot segue normal): %s", e)
    await bot.start(BOT_TOKEN)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        log.info("Encerrado pelo usuario.")
