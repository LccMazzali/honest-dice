# 🎲 Honest Dice — Provably Fair Dice Bot

Bot do Discord para rolagem de dados (**d4, d6, d8, d10, d12, d20, d100**) com **garantia matemática de imparcialidade** usando criptografia **HMAC-SHA256** e **Rejection Sampling** (amostragem por rejeição) para eliminar o viés de módulo.

> Versão do projeto: **v2.0.0** · Feito com Python 3.11 + discord.py 2.3+

---

## ✨ Recursos

- 🎲 7 tipos de dado + expressões complexas (`2d6+1d4+3`, `2d20kh1`, `2d6-1d4+3`)
- 🔒 **Provably Fair**: qualquer rolagem pode ser verificada de forma independente
- 🧮 Rejection Sampling — distribuição **perfeitamente uniforme** (sem modulo bias)
- 🎨 9 comandos slash `/` — fácil de usar
- 🛡️ Server Seed rotacionável + Client Seed personalizável

---

## 🛡️ Como funciona o "Provably Fair"

1. **Server Seed** — 32 bytes criptográficos secretos (o hash SHA-256 fica público)
2. **Client Seed** — string pública que você pode personalizar (`/set_seed`)
3. **Nonce** — contador que aumenta a cada rolagem

**Fórmula:** `resultado = RejectionSample( HMAC-SHA256(server_seed, client_seed + ":" + nonce) )`

Quando o admin usa `/rotate_seed`, o seed antigo é **revelado em texto puro** — e qualquer pessoa pode verificar que as rolagens passadas foram honestas em https://honest-dice.higgsfield.app/verify

---

## 🤖 Comandos

| Comando | Descrição |
|---|---|
| `/roll 1d20+5` | Rola dice com modificador |
| `/r 4d6` | Atalho de `/roll` |
| `/roll 2d8-3 secret:True` | Rolagem secreta (só quem rolou vê) |
| `/history` | Histórico de rolagens |
| `/status` | Status do sistema Provably Fair |
| `/verify <seed> <client> <nonce> <faces> <result>` | Verificação independente |
| `/set_seed <seed>` | Define seu Client Seed |
| `/rotate_seed` | Rotaciona o Server Seed (apenas admin) |
| `/test_fairness` | Teste chi-quadrado (apenas admin) |

---

## 🚀 Deploy 24/7 — Render.com (gratuito)

Este repositório está preparado para rodar no **Render (Background Worker)** — que no plano gratuito **não dorme**, mantendo o bot online 24/7.

### Opção A — Deploy automático via Blueprint (mais simples)

1. Faça **upload deste repositório** para o GitHub (ou dê push):
   ```bash
   git init -b main
   git add .
   git commit -m "Honest Dice Bot"
   git remote add origin https://github.com/SEU_USUARIO/honest-dice.git
   git push -u origin main
   ```
2. No [Render](https://render.com): **New → Blueprint → conectar o GitHub → selecionar `honest-dice` → Apply**
3. No serviço criado (`honest-dice-bot`): **Environment** → adicionar a variável abaixo → **Save**

   | Key | Value |
   |---|---|
   | `DISCORD_BOT_TOKEN` | *(seu token do Discord Developer Portal)* |

4. **Manual Deploy → Deploy latest commit** e confira nos **Logs**:
   ```
   Bot conectado como: Honest Dice Bot#2648 (ID: 1530349265216475247)
   ```

### Opção B — Web Service "clássico" (sem Blueprint)

1. **New → Web Service** → conecte o repo
2. **Runtime:** Docker → `Dockerfile` (o build é automático)
3. **Environment** → adicionar `DISCORD_BOT_TOKEN`
4. **Create Web Service**

> O `render.yaml` e o `Dockerfile` já estão no repositório e prontos para uso.

---

## 🐍 Execução local (dev)

```bash
git clone https://github.com/SEU_USUARIO/honest-dice.git
cd honest-dice
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

export DISCORD_BOT_TOKEN="seu_token_aqui"   # Windows: set DISCORD_BOT_TOKEN=...
python main.py
```

---

## 🗂️ Estrutura do projeto

```
honest_dice/
├── main.py              # Ponto de entrada
├── bot/
│   ├── commands.py      # 9 slash commands
│   └── embeds.py        # mensagens formatadas
├── crypto/
│   ├── provably_fair.py # HMAC-SHA256 + Rejection Sampling
│   └── state.py         # seeds / nonce / persistência
├── dice/
│   ├── parser.py        # expressões (2d6+1d4+3, 2d20kh1...)
│   ├── roller.py        # núcleo da rolagem
│   └── history.py       # histórico por servidor
├── Dockerfile           # imagem do Render
├── render.yaml          # blueprint do Render
└── requirements.txt     # discord.py 2.3+
```

---

## 🔗 Links úteis

- 🌐 App web (rolador + verificador): [honest-dice.higgsfield.app](https://honest-dice.higgsfield.app)
- 📊 Dados Provably Fair — verificação no navegador: `/verify`
- 💬 Discord Developer Portal (token do bot): https://discord.com/developers/applications
- Convite do bot: `https://discord.com/api/oauth2/authorize?client_id=1530349265216475247&scope=bot+applications.commands`

---

## ⚖️ Honestidade

Este projeto não usa geração de números pseudo-aleatórios comuns (`random.randint`) para resultados finais — **todo** resultado é derivado de conteúdo criptográfico verificável. Confira você mesmo em `/verify` no site ou no `/verify` do Discord.