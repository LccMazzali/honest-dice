#!/bin/bash
# ============================================================================
# start.sh — Honest Dice Bot
# Usado pelo Render quando NÃO se usa o Dockerfile (runtime Python simples).
# Se você usar o caminho Docker (render.yaml), este arquivo não é necessário.
#
# Render -> Service -> Environment: definir DISCORD_BOT_TOKEN (obrigatório)
# ============================================================================
set -e

echo "[start.sh] Iniciando Honest Dice Bot..."
echo "[start.sh] Token definido: $([ -n \"$DISCORD_BOT_TOKEN\" ] && echo SIM || echo NAO)"

if [ -z "$DISCORD_BOT_TOKEN" ]; then
  echo "[ERRO] Variável DISCORD_BOT_TOKEN não está definida." >&2
  exit 1
fi

exec python3 main.py