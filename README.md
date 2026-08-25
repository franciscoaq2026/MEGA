# Loterias Stats

App web pessoal de análise estatística das loterias da Caixa: histórico de
sorteios, estatísticas com gráficos, geração de jogos por estratégias e
acompanhamento dos seus jogos (manual vs. gerado pelo app) com conferência
automática.

Duas modalidades, escolhidas pelos extremos opostos que ocupam:

| | Aposta | Prêmio principal | Ganhar algo | Preço |
| --- | --- | --- | --- | --- |
| **Mega-Sena** | 6 de 60 | 1 em 50.063.860 | 1 em 2.298 | R$ 6,00 |
| **Lotofácil** | 15 de 25 | 1 em 3.268.760 | **1 em 9** | R$ 3,50 |

> **Aviso importante (e visível no app):** cada sorteio é independente e
> estatisticamente aleatório — **nenhuma estratégia aumenta a chance real de
> acerto**. A única coisa que muda a probabilidade é jogar mais dezenas ou mais
> bilhetes, pagando proporcionalmente por isso. As estatísticas aqui são
> exploração de dados e entretenimento, não previsão. O app inclui inclusive um
> *backtest* que demonstra isso com os próprios dados.

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

O slug da loteria (`megasena`, `lotofacil`) entra na URL das três fontes:

1. **API da Caixa** (a mesma do site oficial):
   `https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}[/{concurso}]`
2. **Fallback automático**: `https://api.guidi.dev.br/loteria/{slug}/...`
   (se a Caixa falhar, o app passa a usar o fallback na mesma sincronização)
3. **Espelho estático no GitHub** (`maickon/free-apiloterias`) — a única fonte
   que responde a partir de um datacenter, já que Caixa e guidi bloqueiam IPs
   que não sejam residenciais. Cobre as duas modalidades.
4. **Plano C — importar CSV** (botão na tela Sorteios): arquivo com colunas
   `concurso, data, dezena1..dezenaN`, separado por `,` ou `;`, com ou sem
   cabeçalho, datas em `dd/mm/aaaa` ou `aaaa-mm-dd`. `N` é o que a loteria
   aberta sorteia (6 na Mega, 15 na Lotofácil) e o arquivo é validado contra
   ela — um CSV da outra modalidade é recusado, não importado pela metade.

Tudo fica em cache no SQLite (`backend/data/megasena.db`), então o app segue
funcionando se as APIs caírem. Cada loteria tem um histórico embutido
(`backend/data/seed_megasena.json`, `seed_lotofacil.json`) carregado
automaticamente quando o banco está vazio — útil em hospedagem serverless,
onde o disco é efêmero.

## Funcionalidades

Todas valem para as duas loterias — o app é parametrizado por
`backend/app/lotteries.py`, nada assume "6 de 60".

- **Sorteios**: histórico completo, sincronização incremental em lotes com
  progresso, importação de CSV.
- **Estatísticas**: frequência por número (janelas: todos/100/50/25/10),
  quentes/frios, mapa de calor, atraso atual, pares×ímpares (observado vs.
  teórico), distribuição da soma, duplas mais frequentes.
- **Raio-X de um sorteio**: mostra onde cada dezena sorteada estava no
  ranking de frequência/atraso **na véspera** do concurso e quanto os mais
  quentes/mais atrasados teriam acertado — o teste honesto de "dava para
  prever?" (spoiler: não dava).
- **Gerar jogos**: aleatório puro, ponderado por frequência, atrasados e
  balanceado; opção **anti-rateio** (evita combinações populares — não muda a
  chance, mas evita dividir prêmio); painel de **probabilidades reais** por
  faixa, com o custo equivalente; **backtest** das estratégias contra o
  histórico.
- **Probabilidades**: a chance exata de cada faixa para todos os tamanhos de
  aposta que a Caixa aceita, com custo; quanto volta pelas faixas de prêmio
  fixo; para onde vai o dinheiro apostado; e o **teste do qui-quadrado** sobre
  o histórico, com a distribuição observada de cada indicador sobreposta à
  teórica. É a evidência, com os dados do próprio usuário, de que não há
  padrão a explorar.
- **Fábrica**: filtros por indicador, termômetro de tipicidade e fechamentos
  (roda completa e reduzida, com a garantia verificada por força bruta antes
  de mostrar). Os indicadores são escolhidos por loteria — ver abaixo.
- **Meus jogos**: registre seu jogo manual e o gerado pelo app para o mesmo
  concurso; conferência automática (acertos + faixa) quando o resultado é
  sincronizado; painel comparativo você × app.

### Por que os filtros mudam entre as loterias

Um indicador que separa bem "6 de 60" pode não dizer nada em "15 de 25". O
caso mais claro é **dezenas consecutivas**: medindo os 3.657 concursos da
Lotofácil no histórico embutido, 4+ números seguidos aparecem em **87%** dos
sorteios — marcar 15 de 25 força sequências. O mesmo limiar na Mega ocorre em
0,2%. Por isso a Lotofácil não filtra por consecutivos e usa **miolo** no
lugar; e o limiar de "desenho no volante" (anti-rateio) é 4 na Mega e 9 na
Lotofácil, que é onde a raridade se equipara.

Na direção oposta, **repetidas do concurso anterior** é o padrão mais estável
da Lotofácil: como 15 das 25 dezenas saem a cada sorteio, a média medida é
exatamente 9.

### O que a aba Probabilidades mostra da Lotofácil

Medido sobre os 3.657 concursos do histórico embutido:

- **Qui-quadrado das frequências: 24,2 com 24 graus de liberdade** (p = 0,45).
  Sob acaso puro o valor esperado da estatística é igual aos graus de
  liberdade — ou seja, o resultado é praticamente o do acaso perfeito. A dezena
  mais sorteada está só 4,6% acima da média. Não existe "dezena quente".
- **Toda distribuição observada coincide com a teórica**: pares (média 7,2),
  primos (5,4), moldura (9,6), miolo (5,4), múltiplos de 3 (4,8), repetidas
  do concurso anterior (9,0) e soma (195,2 contra 195 teóricos).
- **25,67% de qualquer aposta volta pelas faixas de prêmio fixo** (R$ 7, R$ 14
  e R$ 35 para 11, 12 e 13 acertos). Essa fração é constante de 15 a 20
  dezenas, porque uma aposta de k dezenas é exatamente C(k,15) apostas simples.
- **Chance de ganhar alguma coisa**: 1 em 9,4 com 15 dezenas; 1 em 1,7 com 18;
  1 em 1,06 com 20 — que custa R$ 54.264,00.

O veredito do teste tem três níveis e é deliberadamente cauteloso: um teste a
5% "reprova" 1 de cada 20 históricos honestos, então um p entre 0,01 e 0,05
é reportado como flutuação normal, não como viés. A Mega-Sena cai justamente
nesse caso (p = 0,03) — e a tela explica por que isso não é evidência de nada.

## Deploy (Vercel + Turso)

O app roda num **único projeto Vercel**: o frontend é servido como estático e
o FastAPI roda como **uma função Python** em `/api` (arquivo `api/index.py`).
Como o disco das funções serverless é efêmero, o banco em produção é o
**Turso** (SQLite remoto/libSQL) — o `db.py` usa Turso quando a variável
`TURSO_DATABASE_URL` está definida, e cai para SQLite local caso contrário.

Os jogos salvos ficam no `localStorage` **do navegador** — não dependem do
servidor nem se perdem em deploys.

### Passo a passo

1. **Crie o banco no Turso** e pegue as credenciais:
   ```bash
   turso db create megasena
   turso db show megasena --url          # -> TURSO_DATABASE_URL
   turso db tokens create megasena       # -> TURSO_AUTH_TOKEN
   ```
2. **Popule o histórico uma vez, da sua máquina** (evita os limites de tempo
   das funções do Vercel). Sem argumentos, semeia as duas loterias:
   ```bash
   cd backend
   export TURSO_DATABASE_URL="libsql://...turso.io"
   export TURSO_AUTH_TOKEN="..."
   .venv/bin/pip install libsql
   .venv/bin/python seed_turso.py                    # mega + lofa
   .venv/bin/python seed_turso.py --loteria lofa     # só a Lotofácil
   ```
3. **Importe o repositório no Vercel** como projeto único:
   - *Framework Preset*: **Other** (o `vercel.json` já define build e saída).
     Não use o preset “Services”.
   - *Root Directory*: a raiz do repositório.
   - Em *Environment Variables*, adicione `TURSO_DATABASE_URL` e
     `TURSO_AUTH_TOKEN`.
4. **Deploy.** O Vercel builda o frontend, sobe a função Python e encaminha
   `/api/*` para o FastAPI. Confira em `/api/status` que `db_backend` é
   `turso`.

Depois disso o app já abre com todo o histórico, e o botão “Sincronizar”
só busca os concursos novos.

## Estrutura

```
backend/
  app/
    lotteries.py   # registro das loterias — parametriza todo o resto
    main.py        # FastAPI, CORS, montagem das rotas (com e sem /api)
    db.py          # SQLite/Turso (cache de sorteios + meta + apostas)
    fetcher.py     # API da Caixa + fallback guidi + espelho GitHub
    csv_utils.py   # parser de CSV (importação e seed)
    stats.py       # estatísticas puras (frequência, atraso, soma, raio-x…)
    analysis.py    # indicadores de um jogo + faixas típicas + termômetro
    generator.py   # estratégias de geração + odds + fechamentos + anti-rateio
    checker.py     # conferência de apostas + backtest
    routers/       # draws.py, stats.py, games.py, bets.py, auth.py
  data/            # seed_megasena.json, seed_lotofacil.json
  tests/           # pytest
frontend/
  src/
    pages/         # Hub, Dashboard, Sorteios, Estatisticas, GerarJogos,
                   # Fabrica, MeusJogos
    components/    # Layout, Ball, Card, Volante, Disclaimer…
    lib/           # lotteries.js (espelha o backend), api.js, bets.js,
                   # modalidades.js (catálogo comparativo das 11 da Caixa)
```

Para acrescentar uma loteria, o caminho é declarar em `backend/app/lotteries.py`
e em `frontend/src/lib/lotteries.js`. Se ela tiver mecânica diferente (colunas
posicionais, trevos, dois sorteios), aí é preciso mexer nos motores.
