# Honest Dice — Provably Fair Dice Bot

Discord bot for rolling dice (d4, d6, d8, d10, d12, d20, d100) with verifiable fairness:
HMAC-SHA256 + Rejection Sampling, so results are uniform with zero modulo bias.

**Python 3.11 · discord.py 2.3+**

## Commands

| Command | Description |
|---|---|
| `/roll 1d20+5` | Roll dice with modifier |
| `/r 4d6` | Shortcut for `/roll` |
| `/roll 2d8-3 secret:True` | Secret roll (roller only) |
| `/history` | Roll history |
| `/status` | Provably Fair status |
| `/verify <seed> <client> <nonce> <faces> <result>` | Verify a roll |
| `/set_seed <seed>` | Set your Client Seed |
| `/rotate_seed` | Rotate Server Seed (admin) |
| `/test_fairness` | Chi-square test (admin) |

## 🛡️ ## How it works

result = RejectionSample( HMAC-SHA256(server_seed, client_seed + ":" + nonce) )

Server Seed stays secret (hash is public); when rotated, the old seed is revealed so anyone can verify past rolls.

## Deploy (Render — free)

1. Push this repo to GitHub
2. Render → **New → Blueprint** → connect the repo → **Apply**
3. Add env var: `DISCORD_BOT_TOKEN` (your bot token)
4. **Manual Deploy → Deploy latest commit**
5. Logs show: `Bot connected as: Honest Dice Bot#2648`

The bot serves `GET /health` (port `$PORT`) so free uptime monitors keep it awake 24/7.

## Run locally

pip install -r requirements.txt
export DISCORD_BOT_TOKEN="your_token"
python main.py

## 🗂️ Project layout

main.py          Entry point
bot/             Slash commands
crypto/          HMAC-SHA256 + Rejection Sampling
dice/            Parser, roller, history
Dockerfile       Render build
render.yaml      Render blueprint
---

## 🔗 Useful Links

|- 🌐 Web app: [honest-dice.higgsfield.app](https://honest-dice.higgsfield.app)
|- 📊 Provably Fair dice — verify in your browser: `/verify`
|- 💬 Discord Developer Portal (bot token): https://discord.com/developers/applications
|- Bot invite: `https://discord.com/api/oauth2/authorize?client_id=1530349265216475247&scope=bot+applications.commands`

---

## ⚖️ Honesty

This project does not use ordinary pseudo-random number generation (`random.randint`) for final results — **every** result is derived from verifiable cryptographic content. Check it yourself at `/verify` on the web app or through the Discord `/verify` command.
