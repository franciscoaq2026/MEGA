# Mega-Sena Stats

App web pessoal de análise estatística da Mega-Sena: histórico de sorteios,
estatísticas com gráficos, geração de jogos por estratégias e acompanhamento
dos seus jogos (manual vs. gerado pelo app) com conferência automática.

> **Aviso importante (e visível no app):** cada sorteio da Mega-Sena é
> independente e estatisticamente aleatório — **nenhuma estratégia aumenta a
> chance real de acerto**. As estatísticas aqui são exploração de dados e
> entretenimento, não previsão. O app inclui inclusive um *backtest* que
> demonstra isso com os próprios dados.

## Stack

| Camada | Tecnologia |
| --- | --- |
| Frontend | React 19 + Vite 7 + Tailwind CSS 4 + Recharts (SPA com HashRouter) |
| Backend | Python 3.11+ / FastAPI |
| Banco | SQLite (cache local dos sorteios — dado público e re-obtível) |
| Jogos salvos | `localStorage` do navegador (com exportar/importar backup JSON) |

## Rodar localmente

Backend (porta 8000):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Frontend (porta 5173):

```bash
cd frontend
npm install
npm run dev
```

Abra <http://localhost:5173> — o Vite encaminha `/api` para o backend.
No primeiro uso, vá em **Sorteios → Sincronizar sorteios** para baixar o
histórico completo (só baixa o que falta nas próximas vezes).

### Testes do backend

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Fontes de dados

1. **API da Caixa** (a mesma do site oficial):
   `https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena[/{concurso}]`
2. **Fallback automático**: `https://api.guidi.dev.br/loteria/megasena/...`
   (se a Caixa falhar, o app passa a usar o fallback na mesma sincronização)
3. **Plano C — importar CSV** (botão na tela Sorteios): arquivo com colunas
   `concurso, data, dezena1..dezena6`, separado por `,` ou `;`, com ou sem
   cabeçalho, datas em `dd/mm/aaaa` ou `aaaa-mm-dd`.

Tudo fica em cache no SQLite (`backend/data/megasena.db`), então o app segue
funcionando se as APIs caírem. Se existir `backend/data/seed_megasena.csv`,
ele é carregado automaticamente quando o banco está vazio (útil em
hospedagem serverless, onde o disco é efêmero).

## Funcionalidades

- **Sorteios**: histórico completo, sincronização incremental em lotes com
  progresso, importação de CSV.
- **Estatísticas**: frequência por número (janelas: todos/100/50/25/10),
  quentes/frios, mapa de calor 1–60, atraso atual, pares×ímpares
  (observado vs. teórico), distribuição da soma, duplas mais frequentes.
- **Raio-X de um sorteio**: mostra onde cada dezena sorteada estava no
  ranking de frequência/atraso **na véspera** do concurso e quanto os
  "6 mais quentes"/"6 mais atrasados" teriam acertado — o teste honesto de
  "dava para prever?" (spoiler: não dava).
- **Gerar jogos** (1–20 jogos, 6–20 dezenas): aleatório puro, ponderado por
  frequência, atrasados e balanceado; opção **anti-rateio** (evita
  combinações populares — não muda a chance, mas evita dividir prêmio);
  painel de **probabilidades reais** (sena/quina/quadra, custo equivalente);
  **backtest** das estratégias contra o histórico.
- **Meus jogos**: registre seu jogo manual (volante 1–60) e o jogo gerado
  pelo app para o mesmo concurso; conferência automática (acertos + faixa)
  quando o resultado é sincronizado; painel comparativo você × app.

## Deploy (Vercel)

O `vercel.json` na raiz declara os dois serviços: frontend (Vite) em `/` e
backend (FastAPI) em `/api`. Pontos importantes do modelo serverless:

- O disco é efêmero: o SQLite vai para `/tmp` e é repovoado a partir do
  `seed_megasena.csv` (se presente) a cada cold start; a sincronização busca
  só os concursos que faltam.
- Os jogos salvos ficam no `localStorage` **do navegador do usuário** — não
  se perdem em deploys. Use Exportar/Importar backup para trocar de aparelho.

## Estrutura

```
backend/
  app/
    main.py        # FastAPI, CORS, montagem das rotas (com e sem /api)
    db.py          # SQLite (cache de sorteios + meta)
    fetcher.py     # API da Caixa + fallback guidi
    csv_utils.py   # parser de CSV (importação e seed)
    stats.py       # estatísticas puras (frequência, atraso, soma, raio-x…)
    generator.py   # estratégias de geração + odds + anti-rateio
    checker.py     # conferência de apostas + backtest
    routers/       # draws.py, stats.py, games.py
  tests/           # pytest
frontend/
  src/
    pages/         # Dashboard, Sorteios, Estatisticas, GerarJogos, MeusJogos
    components/    # Layout, Ball, Card, Volante, Disclaimer…
    lib/           # api.js, bets.js (localStorage), format.js
```
