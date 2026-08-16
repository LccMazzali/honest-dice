# ============================================================================
# Dockerfile — Honest Dice Bot
# ============================================================================
# Build:
#   docker build -t honest-dice .
#
# Run:
#   docker run -d \
#     --name honest-dice \
#     -e DISCORD_BOT_TOKEN="seu_token_aqui" \
#     -e LOG_LEVEL=INFO \
#     -v honest_dice_data:/app/data \
#     honest-dice
#
# O volume /app/data armazena:
#   - bot_state.json       (Server/Client seeds, nonce)
#   - history/             (histórico por servidor)
#   - honest_dice.log      (logs do bot)
# ============================================================================

FROM python:3.11-slim

# ---------------------------------------------------------------------------
# Ambiente
# ---------------------------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV LOG_FILE=/app/data/honest_dice.log

# ---------------------------------------------------------------------------
# Diretório da aplicação
# ---------------------------------------------------------------------------

WORKDIR /app

# ---------------------------------------------------------------------------
# Dependências primeiro (cache de camada Docker)
# ---------------------------------------------------------------------------

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Código da aplicação
# ---------------------------------------------------------------------------

COPY . .

# ---------------------------------------------------------------------------
# Volume para dados persistentes (estado + histórico + logs)
# ---------------------------------------------------------------------------

RUN mkdir -p /app/data
VOLUME ["/app/data"]

# ---------------------------------------------------------------------------
# Usuário não-root (segurança)
# ---------------------------------------------------------------------------

RUN useradd -m -u 1000 honstdice && chown -R honstdice:honstdice /app
USER honstdice

# ---------------------------------------------------------------------------
# Saúde
# ---------------------------------------------------------------------------

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
    CMD python3 -c "import os; exit(0 if os.path.exists('/app/data/bot_state.json') else 1)"

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

CMD ["python3", "main.py"]