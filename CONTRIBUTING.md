# Contribuindo com o Gedos

Obrigado pelo interesse em contribuir! Este guia explica como configurar o ambiente, as regras de código e como enviar um Pull Request.

---

## 1. Clonar e rodar localmente

```bash
git clone https://github.com/g-dos/gedos.git
cd gedos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` e defina pelo menos `TELEGRAM_BOT_TOKEN` (obtenha com [@BotFather](https://t.me/BotFather)).

### Rodar

```bash
python gedos.py
```

### Rodar os testes

```bash
pytest tests/ -v
```

Todos os 22 testes devem passar antes de enviar qualquer PR.

### Ollama (opcional)

Para usar o LLM local, instale e inicie o Ollama:

```bash
brew install ollama
ollama pull llama3.3
ollama serve
```

Veja o guia completo em [docs/setup-ollama.md](docs/setup-ollama.md).

---

## 2. Regras de código

### Python

- **Python 3.12+**
- **Type hints** em todas as funções e métodos
- **Docstrings** em todos os métodos públicos
- Sem imports não utilizados
- Sem valores hardcoded — tudo via `config.py`

### Estrutura

```
core/          — config, memory, orchestrator, LLM, copilot
agents/        — terminal, GUI, web
interfaces/    — telegram bot
tools/         — AX tree, mouse, keyboard
tests/         — pytest smoke tests
docs/          — documentação adicional
```

### Formatação

- 4 espaços de indentação
- Linhas com no máximo 120 caracteres
- Strings com aspas duplas
- f-strings quando necessário

---

## 3. Semantic Commits

Todos os commits devem seguir o padrão de commit semântico:

| Prefixo | Quando usar | Exemplo |
|---|---|---|
| `feat` | Nova funcionalidade | `feat: add /screenshot command` |
| `fix` | Correção de bug | `fix: terminal timeout not respected` |
| `docs` | Documentação | `docs: add Ollama setup guide` |
| `refactor` | Refatoração sem mudar comportamento | `refactor: extract routing logic` |
| `test` | Testes | `test: add orchestrator routing tests` |
| `chore` | Manutenção, deps, versão | `chore: bump to v0.5.0` |

### Formato

```
<tipo>: <descrição curta>

<corpo opcional — explique o "porquê", não o "o quê">
```

### Exemplos

```
feat: add web scraping to /web command

Playwright now extracts page title and text content,
returning a summary instead of just confirming navigation.
```

```
fix: copilot sending duplicate suggestions

Added throttling dict to prevent same message type
from being sent to same user within 60 seconds.
```

---

## 4. Como enviar um Pull Request

### Passo a passo

1. **Fork** o repositório no GitHub
2. **Clone** o seu fork:
   ```bash
   git clone https://github.com/SEU-USER/gedos.git
   cd gedos
   ```
3. **Crie uma branch** a partir de `main`:
   ```bash
   git checkout -b feat/minha-feature
   ```
4. **Faça suas mudanças** seguindo as regras de código acima
5. **Rode os testes**:
   ```bash
   pytest tests/ -v
   ```
6. **Commit** com mensagem semântica:
   ```bash
   git commit -m "feat: minha nova feature"
   ```
7. **Push** para o seu fork:
   ```bash
   git push origin feat/minha-feature
   ```
8. **Abra um PR** no GitHub apontando para `main`

### Checklist do PR

- [ ] Testes passando (`pytest tests/ -v`)
- [ ] Commit semântico
- [ ] Type hints em funções novas
- [ ] Docstrings em métodos públicos
- [ ] Sem secrets no código (API keys vão no `.env`)
- [ ] Não quebra Pilot Mode nem Copilot Mode

### O que evitar

- Não adicione dependências cloud ao core — Gedos é local first
- Não use screenshots como método primário de leitura de tela — AX Tree primeiro
- Não hardcode valores — use `config.py`
- Não commite `.env` ou credenciais

---

## 5. Reportando bugs

Abra uma [issue](https://github.com/g-dos/gedos/issues) com:

1. O que você fez (comando/ação)
2. O que esperava acontecer
3. O que aconteceu de fato
4. Versão do Gedos (`python gedos.py --version` ou veja `gedos.py`)
5. macOS version

---

## Dúvidas?

Abra uma issue ou entre em contato via Telegram.

---

*Built by [@g-dos](https://github.com/g-dos)*
