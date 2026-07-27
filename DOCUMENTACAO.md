# Loterias Stats — Documentação completa (funcional + técnica)

> Este documento explica **o que o app faz, como usar e como foi implementado**,
> com detalhe suficiente para que outra IA (ou desenvolvedor) entenda o projeto
> inteiro sem precisar de contexto adicional.
>
> - **Produção**: https://mega-omega-blond.vercel.app
> - **Repositório**: `franciscoaq2026/MEGA`, branch `claude/megasena-stats-app-dkjydf`
> - **Stack**: React 19 + Vite 7 + Tailwind 4 + Recharts (frontend) · Python 3.11/FastAPI (backend) · SQLite local / Turso-libSQL em produção · Vercel (frontend estático + função Python)

---

## 0. Princípio de honestidade (regra de projeto)

Cada sorteio é **independente e uniformemente aleatório**. Nenhuma estatística,
estratégia ou filtro altera a probabilidade real de acerto de uma combinação
(sena = 1 em 50.063.860 para 6 dezenas; 15 acertos = 1 em 3.268.760 para 15
dezenas — sempre). O app trata estatística como **exploração de dados e
organização de jogos**, nunca como previsão — e diz isso na interface (rodapé
fixo em todas as telas, avisos nas respostas da API, e ferramentas que
*demonstram* a aleatoriedade, como o backtest e o raio-X). Qualquer análise
deste projeto deve preservar esse princípio.

A única exceção real, e o app é explícito sobre ela: **aumentar o número de
dezenas da aposta muda a probabilidade de verdade**, porque uma aposta de k
dezenas equivale a C(k, escolher) apostas simples — e custa exatamente isso.
É o que a aba Fábrica → Fechamento calcula, com a garantia verificada por
força bruta antes de exibir.

### Loterias suportadas

| | Aposta | Sorteia | Faixas | Prêmio principal | Ganhar algo | Preço |
| --- | --- | --- | --- | --- | --- | --- |
| **Mega-Sena** (`mega`) | 6 a 20 de 60 | 6 | 6/5/4 | 1 em 50.063.860 | 1 em 2.298 | R$ 6,00 |
| **Lotofácil** (`lofa`) | 15 a 20 de 25 | 15 | 15/14/13/12/11 | 1 em 3.268.760 | 1 em 9 | R$ 3,50 |

Todo o backend é parametrizado por `backend/app/lotteries.py`; nada assume
"6 de 60". A Lotomania foi removida do app (era `loto`): ficava em último lugar
nas duas dimensões que importam — 1 em 11.372.635 no prêmio principal e apenas
1 em 88 para ganhar algo, com prêmio-base de R$ 500 mil.

---

## 1. Conceitos e vocabulário

| Termo | Significado no app |
| --- | --- |
| **Concurso** | Um sorteio oficial numerado (1, 2, 3, … ~2994+) |
| **Dezena** | Um número de 1 a 60 |
| **Jogo / aposta** | Um conjunto de **6 a 20 dezenas** (6 = aposta simples; 7–20 = aposta múltipla, que equivale a C(k,6) apostas simples) |
| **Quantos jogos** | Quantidade de **apostas independentes** a gerar — o usuário controla (1–20 na tela Gerar; 1–50 na Fábrica) |
| **Dezenas por jogo** | Tamanho de **cada** aposta (6–20) |
| **Jogo manual** | Aposta digitada pelo usuário (origem `manual`) |
| **Jogo do app** | Aposta gerada por alguma ferramenta do site (origem `app`, com o nome da estratégia) |
| **Fechamento** | Conjunto de vários jogos derivados de 7–20 dezenas escolhidas (ver §6.3) |

### Esclarecimento importante (fonte comum de confusão)

- O gerador **gera exatamente o número de apostas** definido em "Quantos
  jogos". Se o usuário pede 2, saem 2 cartões; cada cartão tem as bolas verdes
  = as dezenas daquela aposta.
- As **etiquetas cinzas** sob cada jogo gerado (ex.: `soma 167 · P 3 · primos 1
  · moldura 5 · seq 2 · rep 2`) **não são números da aposta** — são
  *estatísticas descritivas* daquele jogo (soma das dezenas, quantidade de
  pares, de primos, etc.), úteis para conferir os filtros.
- O **Fechamento** é a única ferramenta que gera "vários jogos de uma vez" por
  natureza: o usuário escolhe 7–20 dezenas e o app monta o **conjunto** de
  apostas que cobre essas dezenas com garantia matemática. Isso é o
  comportamento esperado de um fechamento/desdobramento, não um bug.

---

## 2. Estrutura do repositório

```
MEGA/
├── vercel.json               # build do frontend + função Python + rewrites /api/*
├── requirements.txt          # deps da função Python no Vercel (inclui libsql)
├── api/
│   └── index.py              # entrypoint Vercel: expõe o app FastAPI (ASGI)
├── backend/
│   ├── requirements.txt      # deps de desenvolvimento local
│   ├── requirements-dev.txt  # + pytest
│   ├── seed_turso.py         # script opcional: popular o Turso a partir da máquina local
│   ├── .env.example          # TURSO_DATABASE_URL / TURSO_AUTH_TOKEN
│   ├── data/
│   │   └── seed_megasena.json  # histórico embutido: 2.994 concursos com datas
│   ├── app/
│   │   ├── main.py           # FastAPI, CORS, lifespan(init_db), monta rotas com e sem /api
│   │   ├── db.py             # camada de banco DUAL: SQLite local OU Turso (libsql)
│   │   ├── fetcher.py        # busca resultados: Caixa → guidi → espelho GitHub (maickon)
│   │   ├── csv_utils.py      # parser de CSV (importação manual)
│   │   ├── stats.py          # estatísticas básicas + raio-X
│   │   ├── analysis.py       # métricas avançadas, faixas históricas, termômetro
│   │   ├── generator.py      # estratégias, filtros avançados, odds, fechamentos, anti-rateio
│   │   ├── checker.py        # conferência de apostas + backtest
│   │   └── routers/
│   │       ├── draws.py      # /status /draws /sync /import-csv
│   │       ├── stats.py      # /stats/*
│   │       └── games.py      # /generate /generate-advanced /odds /score /wheel /check /backtest
│   └── tests/                # 25 testes (pytest): api, stats, generator, checker, factory
└── frontend/
    └── src/
        ├── App.jsx           # rotas (HashRouter; Estatísticas com React.lazy)
        ├── pages/            # Dashboard, Sorteios, Estatisticas, GerarJogos, Fabrica, MeusJogos
        ├── components/       # Layout, Ball, Card, Volante, Disclaimer, MetricBadges
        └── lib/
            ├── api.js        # fetch wrapper (/api)
            ├── bets.js       # apostas do usuário no localStorage + export/import JSON
            └── format.js     # datas, moeda e números em pt-BR
```

---

## 3. Dados: fontes, cache e a questão do bloqueio por IP

### 3.1 O problema central

A API oficial da Caixa (`servicebus2.caixa.gov.br/portaldeloterias/api/megasena`)
e o fallback `api.guidi.dev.br` **bloqueiam requisições de IPs de datacenter**
(retornam 403). Funcionam de IP residencial brasileiro (navegador do usuário),
mas **não do Vercel**. Isso quebrou a sincronização em produção e guiou o design.

### 3.2 A cadeia de fontes (fetcher.py)

Ordem de tentativa por concurso, com "stickiness" (se a Caixa falha uma vez na
sessão de sync, as próximas já começam pelo fallback):

1. **Caixa** (oficial, mais fresca) — só funciona em IP residencial;
2. **guidi.dev.br** (espelho da Caixa) — idem;
3. **maickon/free-apiloterias no GitHub raw** — espelho estático em
   `raw.githubusercontent.com/maickon/free-apiloterias/master/database/megasena/{N}.json`
   (e `_ultimo.json`), **formato idêntico ao payload da Caixa**. GitHub **não
   bloqueia** datacenter → funciona no Vercel, mas o robô que o atualizava
   também foi bloqueado pela Caixa (parou no concurso ~2995, abr/2026);
4. **O navegador do usuário** (a fonte que resolve o frescor): ao clicar em
   "Sincronizar", o frontend também busca os concursos novos **direto da
   Caixa/guidi a partir do navegador** — o IP residencial do usuário não é
   bloqueado — e envia os payloads brutos para `POST /api/import-payloads`,
   onde o servidor valida com o mesmo `parse_payload()` e grava no banco.
   Assim, cada visita do usuário atualiza o app até o concurso mais recente,
   sem depender de nenhum espelho.

`parse_payload()` normaliza qualquer uma das três para
`{concurso:int, data:"YYYY-MM-DD", dezenas:[6 ints ordenados], proximo:{...}}`.

### 3.3 Histórico embutido (seed)

`backend/data/seed_megasena.json`: **2.994 concursos reais com data**
(montado a partir do `_todos.json` do maickon). Usos:

- **Desenvolvimento local**: `init_db()` auto-carrega o seed se o banco estiver
  vazio (desligável com `MEGASENA_AUTOSEED=0`, usado nos testes).
- **Produção**: o endpoint `/sync` usa o seed como fonte instantânea do volume
  histórico (sem rede) e só busca da rede o que for **mais novo** que o seed.

### 3.4 Sincronização (`POST /api/sync?max_batch=200`)

Incremental e em lotes (o frontend chama em loop até `remaining == 0`, exibindo
progresso — isso respeita o `maxDuration` da função serverless):

1. busca o "último" na cadeia de fontes → se **todas** falham, usa só o seed
   (`_sync_from_seed`);
2. calcula os concursos **faltantes ou sem data** (`concursos_com_data()`);
3. resolve cada um: primeiro do seed (cópia local), depois da rede
   (`fetch_many`, httpx assíncrono com semáforo de concorrência 8);
4. grava via upsert (`INSERT OR REPLACE`) e retorna
   `{source, latest_remote, added, remaining, total_local, proximo}`.

### 3.5 Plano C — CSV manual (`POST /api/import-csv`)

Aceita `concurso, data, dezena1..dezena6` (separador `,` ou `;`, com/sem
cabeçalho, datas `dd/mm/aaaa` ou ISO; linhas inválidas são reportadas e
puladas).

### 3.6 Banco de dados dual (db.py)

- **Local**: SQLite em `backend/data/megasena.db` (ou `MEGASENA_DB_PATH`).
- **Produção**: **Turso/libSQL** (SQLite remoto persistente) quando
  `TURSO_DATABASE_URL` está definida — necessário porque o disco das funções
  do Vercel é efêmero. Cliente `libsql`, conexão por requisição.
- A camada usa **apenas o subconjunto comum da DB-API** (placeholders `?`,
  `cursor.description`, `execute/commit`) para os dois drivers funcionarem
  com o mesmo código. Schema:

```sql
CREATE TABLE draws (concurso INTEGER PRIMARY KEY, data TEXT NOT NULL,
                    d1..d6 INTEGER NOT NULL);          -- dezenas ordenadas
CREATE TABLE meta  (key TEXT PRIMARY KEY, value TEXT); -- ex.: 'proximo' (JSON)
```

- `/api/status` expõe `db_backend: "turso" | "sqlite"` para diagnóstico.

### 3.7 Apostas do usuário — localStorage (frontend/lib/bets.js)

As apostas **não ficam no banco do servidor**: ficam no `localStorage` do
navegador (chave `megasena.bets.v1`), com **exportar/importar backup JSON**.
Motivos: privacidade, zero dependência de auth, e imunidade a redeploys.
Schema de cada aposta:

```json
{ "id": "uuid", "concurso": 2995, "origem": "manual" | "app",
  "estrategia": null | "aleatorio" | "frequencia" | "atrasados" | "balanceado"
              | "avancado" | "fechamento-completa" | "fechamento-reduzida",
  "dezenas": [4, 17, 23, 38, 45, 59], "criado_em": "ISO-8601" }
```

A conferência é **stateless**: o frontend manda as apostas para `/api/check` e
recebe acertos/faixa — o servidor não guarda nada do usuário.

---

## 4. Telas (frontend) e fluxos de uso

Navegação: **Início · Sorteios · Estatísticas · Gerar jogos · Fábrica · Meus jogos**
(SPA com HashRouter — URLs `/#/rota` — para dispensar rewrites de servidor).

### 4.1 Início (Dashboard)
Último sorteio (bolas), próximo concurso (número, data, prêmio estimado, vindo
do payload da fonte), atalhos, e estado de erro amigável se o backend não sobe.

### 4.2 Sorteios
Lista paginada dos concursos em cache (cards com bolas verdes), botão
**Sincronizar sorteios** (loop de lotes com progresso "baixados X, faltam Y") e
**Importar CSV**.

### 4.3 Estatísticas (carregada sob demanda — React.lazy, por causa do Recharts)
- **Frequência por número** (barras, 60 números) com janelas: todos/100/50/25/10
  e linha de referência do esperado; chips dos 10 mais/menos sorteados.
- **Mapa de calor 1–60** (intensidade = frequência na janela).
- **Atraso atual por número** (barras + referência do atraso esperado ≈ 9).
- **Pares × ímpares**: distribuição observada vs. **teórica** (hipergeométrica
  C(30,k)·C(30,6−k)/C(60,6)) — barra + linha com legenda.
- **Soma das dezenas**: histograma em faixas, média observada vs. teórica (183).
- **Duplas que mais saem juntas** (co-ocorrência, com o valor esperado ao acaso).
- **Raio-X de um sorteio**: para um concurso N, mostra o ranking de frequência
  e o atraso de cada dezena sorteada **na véspera** (usa só `draws[:idx]`), e
  quantas dezenas os "6 mais quentes"/"6 mais atrasados" teriam acertado.
  Ferramenta educacional: demonstra que "dava para prever" é ilusão retrospectiva.

### 4.4 Gerar jogos (estratégias clássicas)
Controles: estratégia (4 cards), **Quantos jogos (1–20)**, **Dezenas por jogo
(6–20)**, toggle anti-rateio. Painel lateral de **probabilidades reais**
(sena/quina/quadra "1 em N" exatos para o tamanho escolhido; custo equivalente
em apostas simples com preço editável). Card de **backtest** (§6.5). Cada jogo
gerado tem botão **"Salvar este jogo"** → vira "jogo do app" no concurso
indicado.

### 4.5 Fábrica de números (3 abas)
1. **Gerador avançado**: gera **exatamente N jogos** (campo "Quantos jogos",
   1–50) que passam em TODOS os filtros ativos: faixas de soma, pares, primos,
   moldura, baixas, repetidas do último sorteio; máximo de consecutivos;
   dezenas fixas (sempre entram) e excluídas (nunca entram); anti-rateio.
   Cada filtro mostra a **faixa típica histórica (p10–p90)** como default.
   Badges cinzas em cada jogo = métricas descritivas (não são dezenas).
2. **Fechamento/desdobramento**: volante para escolher 7–20 dezenas;
   - *Roda completa* (≤11 dezenas): todas as C(k,6) apostas — garantias exatas
     (se H das suas saírem, você tem um jogo com H acertos);
   - *Reduzido* (≤15 dezenas): subconjunto bem menor que garante **quadra** ou
     **quina** SE as 6 sorteadas estiverem entre as escolhidas; a garantia é
     **verificada por força bruta** antes de responder (campo
     `garantia_verificada`).
3. **Termômetro**: avalia qualquer jogo (6–20 dezenas) com **nota 0–100 de
   tipicidade** + detalhamento por critério vs. faixa típica. Explicitamente
   rotulado: mede tipicidade, **não** chance de ganhar.

### 4.6 Meus jogos
- Volante para digitar o **jogo manual** (6 dezenas) e vincular a um concurso
  (default = próximo a fechar).
- Lista **agrupada por concurso**, com duas colunas: *Meu jogo (manual)* ×
  *Jogo do app* — o cenário "2 geradas + 1 manual no mesmo concurso" aparece
  como um card do concurso com 1 aposta na coluna manual e 2 na coluna app.
- **Conferência automática** (`/api/check`): bolas coincidentes destacadas em
  âmbar, badge "X acerto(s)" e faixa (QUADRA/QUINA/SENA) quando ≥4.
- **Painel comparativo você × app**: média de acertos de cada lado, vitórias
  por concurso e empates ("só por curiosidade — tende ao empate").
- **Exportar/Importar backup** (JSON).

---

## 5. API (todos os endpoints)

Prefixo `/api` (as rotas também respondem sem prefixo, pois algumas plataformas
removem o `/api` ao rotear). Erro padrão FastAPI: `{"detail": "mensagem"}`.

| Método e rota | Função |
| --- | --- |
| `GET /api/health` | ping: versão + hora do servidor |
| `GET /api/status` | `{total_draws, ultimo_local, proximo, db_backend}` |
| `GET /api/draws?limit&offset` | lista paginada (desc) |
| `GET /api/draws/{n}` | um concurso |
| `POST /api/sync?max_batch=200` | sincronização incremental (ver §3.4) |
| `POST /api/import-csv` | multipart CSV (plano C) |
| `POST /api/import-payloads` | `{payloads:[<json bruto Caixa/guidi>]}` — enviados pelo navegador do usuário (§3.2 item 4) |
| `GET /api/stats/frequency?window=0\|10\|25\|50\|100` | frequência + hot/cold |
| `GET /api/stats/delay` | atraso atual por número + top 10 |
| `GET /api/stats/parity` | pares×ímpares observado vs. teórico |
| `GET /api/stats/sums` | histograma de soma + médias |
| `GET /api/stats/pairs?limit` | duplas mais frequentes |
| `GET /api/stats/xray/{n}` | raio-X do concurso n (véspera) |
| `GET /api/strategies` | nomes/descrições das estratégias |
| `POST /api/generate` | `{estrategia, jogos≤20, dezenas 6–20, anti_rateio, espalhar}` → jogos + `sobreposicao` |
| `GET /api/odds?dezenas&preco_simples` | probabilidades exatas + custo |
| `GET /api/analysis/ranges` | faixas típicas (p10–p90) de cada indicador |
| `POST /api/generate-advanced` | `{jogos≤50, dezenas, filtros{...}, incluir[], excluir[], anti_rateio}` |
| `POST /api/score` | termômetro: `{dezenas[6–20]}` → nota + critérios |
| `POST /api/wheel` | fechamento: `{dezenas[7–20], tipo: completa\|reduzida, garantia: 4\|5}` |
| `GET /api/acertos-esperados?dezenas` | régua: distribuição de acertos de uma aposta de N dezenas |
| `POST /api/check` | conferência: `{apostas:[{concurso, dezenas}]}` → acertos, faixa e `avaliacao` |
| `POST /api/backtest?ultimos=100` | simulação honesta das 4 estratégias |

---

## 6. Algoritmos (como foi implementado)

### 6.1 Estratégias clássicas (generator.py)
- **aleatorio**: `random.sample(1..60, k)` — baseline sem viés.
- **frequencia**: amostragem ponderada sem reposição; peso = contagem histórica
  da dezena + 1 (suavização).
- **atrasados**: idem, peso = atraso atual + 1.
- **balanceado**: rejection sampling (até 400 tentativas): metade do jogo vem
  dos 30 mais frequentes, metade dos 30 menos; aceita se pares ∈ [k/2−1,
  k/2+2] e soma ∈ 30,5·k ± 7·k; senão devolve o candidato de soma mais próxima.
- Jogos repetidos dentro de um mesmo pedido são evitados.

### 6.2 Anti-rateio (`padrao_popular`)
Detecta combinações que **muita gente joga** (não muda probabilidade de
ganhar; reduz divisão do prêmio): todas ≤31 (datas de aniversário), progressão
aritmética, ≥4 consecutivos, todas na mesma coluna do volante, sena já sorteada
no passado. Com o toggle ligado, o gerador re-sorteia até sair combinação
"impopular"; com ele desligado, os motivos aparecem como aviso no jogo.

### 6.3 Fechamentos (`roda_completa`, `fechamento_reduzido`)
- **Roda completa**: todas as C(k,6) combinações das k dezenas (limitada a
  k≤11 → ≤462 jogos). Garantia exata por construção.
- **Reduzido**: problema de *set cover* — cobrir todos os C(k,6) resultados
  possíveis (dentro das k dezenas) com apostas que compartilhem ≥`garantia`
  dezenas com qualquer um deles. Heurística **gulosa** escolhendo sempre a
  aposta que cobre mais alvos restantes, com coberturas pré-computadas como
  **bitmasks** (inteiros Python; `bit_count()`) para velocidade — k=15/quadra
  em ~6s. Ao final, a garantia é **re-verificada por força bruta** e o campo
  `garantia_verificada` só vem `true` se a cobertura for total. Limites: k≤15
  (reduzido), garantia ∈ {4,5}.

### 6.4 Probabilidades (`odds`)
Distribuição hipergeométrica exata: para um jogo de k dezenas,
`P(m acertos) = C(6,m)·C(54,k−m)/C(60,k)`. Valores de referência validados em
teste: sena 6 dezenas = 1/50.063.860; quadra = 1/2.332; 20 dezenas → sena
1/1.292 (C(20,6)=38.760 combinações).

### 6.5 Backtest honesto (checker.py)
Para cada um dos últimos N concursos (default 100): gera 1 jogo de cada
estratégia usando **somente** os sorteios anteriores àquele concurso (sem
vazamento de futuro), com RNG semeado pelo número do concurso
(reprodutível), e conta acertos. Esperado pelo acaso:
`escolher · sorteadas / total` — **0,6 acertos/jogo** na Mega (6·6/60) e
**9,0** na Lotofácil (15·15/25). O resultado empírico de todas as estratégias
flutua em torno disso, demonstrando a ausência de poder preditivo. Medido nos
últimos 1.000 concursos da Lotofácil: aleatório 9,07 · frequência 9,03 ·
atrasados 9,01 · balanceado 9,04, com 10,4% a 11,3% dos jogos chegando aos 11
acertos da faixa mínima (o teórico é 10,6%).

### 6.5.1 Régua de acertos (`distribuicao_acertos`, `avaliar_acertos`)
A mesma hipergeométrica de §6.4 lida ao contrário: em vez de "qual a chance da
faixa X", responde **"quantos acertos esperar"** — o que permite julgar um
resultado já saído.

    esperado = k · sorteadas / total
    var      = k · p · (1−p) · (total−k)/(total−1),  p = sorteadas/total

Na Lotofácil simples: 9,00 ± 1,22 acertos, moda 9, e só 10,59% dos jogos (1 em
9) chegam aos 11 que pagam. O veredito de `avaliar_acertos` usa 1 desvio-padrão
como régua — 8 a 10 acertos é *dentro do esperado*, 11+ é *acima*, ≤7 é
*abaixo* — e vem embutido em cada linha de `POST /api/check`, com as caudas
estritas (quantos % dos jogos possíveis fariam menos e mais acertos). É o que
impede a leitura errada de que "9 de 15" foi um bom jogo: é exatamente a média
de qualquer combinação.

### 6.5.2 Sobreposição entre bilhetes (`piso_sobreposicao`, `resumo_sobreposicao`)
Com 2 bilhetes de k dezenas, a distribuição CONJUNTA dos acertos depende só de
quantas dezenas eles compartilham — quais dezenas são é irrelevante. Isso
encerra a pergunta "qual estratégia acerta mais com vários jogos": nenhuma. O
que existe é sobreposição, e ela tem piso por casa dos pombos:

    piso = max(0, 2k − total)

Mega: 0 (dois jogos podem ser disjuntos). Lotofácil: **5** — dois jogos de 15
dezenas em 25 não podem dividir menos que isso. Por enumeração exata dos
3.268.760 sorteios, 2 bilhetes de 15 dezenas:

| sobreposição | premiar em ≥1 | melhor bilhete | soma dos acertos | retorno fixo |
|---|---|---|---|---|
| 5 ou 6 (piso) | 21,178% | 9,88 | 18,00 | R$ 1,80 |
| 9 (típico sem espalhar) | 20,184% | 9,68 | 18,00 | R$ 1,80 |
| 15 (bilhetes iguais) | 10,589% | 9,00 | 18,00 | R$ 1,80 |

Sobreposição 5 e 6 dão exatamente a mesma chance (15733/74290) — não é
arredondamento. O retorno médio e a soma dos acertos não se movem em nenhum
caso: espalhar redistribui, não aumenta. `gerar(espalhar=True)` usa o piso como
alvo de parada (mirar em "zero repetidas" nunca terminava na Lotofácil) e
`/generate` devolve a sobreposição obtida contra o piso.

### 6.6 Métricas e termômetro (analysis.py)
- **Métricas por jogo**: soma, pares/ímpares, primos, fibonacci, múltiplos de
  3, moldura/miolo (volante 6×10: moldura = 1ª/última linha ou coluna),
  quadrantes, baixas (≤30)/altas, maior sequência consecutiva, terminações
  distintas, repetidas do concurso anterior.
- **Faixas históricas**: para cada indicador, distribuição sobre todo o
  histórico → min/max, média, desvio, percentis p05/p10/p90/p95. A faixa
  p10–p90 é a "faixa típica" usada como default dos filtros.
- **Score (0–100)**: média dos critérios; cada critério vale 100 se o valor cai
  na faixa típica, senão perde 35 pontos por desvio-padrão de distância.
  Classificações: ≥85 "muito dentro do padrão", ≥65 "dentro", ≥45 "um pouco
  fora", <45 "bem atípico". É uma medida de **tipicidade**, não de chance.

### 6.7 Raio-X (stats.py :: xray)
Corta o histórico em `draws[:idx]` (estritamente antes do concurso analisado),
recalcula frequência e atraso naquele instante, e reporta o ranking de cada
dezena sorteada + interseção com os "6 mais quentes" e "6 mais atrasados" da
véspera (tipicamente 0–1 de 6 — o esperado ao acaso é 0,6).

---

## 7. Deploy (Vercel + Turso)

- `vercel.json`: `buildCommand` compila o frontend (`frontend/dist` como
  `outputDirectory`); `functions` declara `api/index.py` com `maxDuration: 60`
  e `includeFiles: backend/data/**` (o seed vai junto da função); `rewrites`
  mandam `/api/(.*)` para a função.
- `api/index.py` insere `backend/` no `sys.path`, importa o `app` FastAPI e
  roda `init_db()` por cold start (idempotente).
- **Variáveis de ambiente na Vercel**: `TURSO_DATABASE_URL` e
  `TURSO_AUTH_TOKEN` (sem elas o backend cai para SQLite em disco efêmero —
  os dados somem entre invocações; o status denuncia via `db_backend`).
- Primeira carga de dados: botão **Sincronizar** no site (usa seed embutido +
  espelho GitHub). Opcional: `backend/seed_turso.py` rodado da máquina do
  usuário (IP residencial alcança a Caixa) para completar até o concurso mais
  recente.
- Cada push na branch dispara redeploy automático.

## 8. Rodando localmente e testes

```bash
# backend (porta 8000) — auto-carrega o seed de 2.994 concursos
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

# frontend (porta 5173, proxy /api -> 8000)
cd frontend && npm install && npm run dev

# testes (25)
cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

Variáveis úteis: `MEGASENA_DB_PATH` (caminho do SQLite), `MEGASENA_AUTOSEED=0`
(desliga a carga automática do seed), `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`
(ativam o backend Turso).

## 9. Limitações conhecidas e decisões de design

1. **Frescor dos dados** depende de alguém abrir o site e clicar em
   "Sincronizar" a partir de um IP residencial (a fase navegador→Caixa faz o
   resto). Se as fontes oficiais bloquearem também CORS do navegador, restam:
   espelho GitHub (defasado) e `seed_turso.py`/CSV manual.
2. **Apostas no localStorage**: não sincronizam entre aparelhos (mitigação:
   exportar/importar backup). Escolha deliberada para evitar auth/banco de
   dados de usuário.
3. **HashRouter** (`/#/rota`): dispensa configuração de rewrites SPA em
   qualquer host, ao custo estético da URL.
4. **Fechamento reduzido é heurístico** (guloso): não é o mínimo teórico de
   jogos, mas a garantia anunciada é sempre verificada por força bruta antes
   de responder.
5. **Limites de tamanho** (k≤11 completa, k≤15 reduzido, lotes de 200 no sync)
   existem para caber no `maxDuration` de 60s da função serverless.
6. **Datas ausentes**: se algum concurso entrar sem data (fontes antigas), o
   sync re-busca automaticamente esses concursos para completar.

## 10. Histórico de commits (resumo da evolução)

1. `a9ed186` scaffold monorepo (FastAPI + React/Vite/Tailwind)
2. `f4bc83a` config inicial de deploy multi-service (depois substituída)
3. `ca74b7b` fontes de dados + cache SQLite + sync incremental + CSV
4. `00e443b` estatísticas + gráficos + raio-X (correção do HashRouter)
5. `9513d63` geração (4 estratégias) + odds + anti-rateio
6. `f970976` meus jogos (manual×app), conferência, comparativo, backtest, 20 dezenas
7. `d51a2d2` polimento de UI/performance + README
8. `aa754e5` deploy single-project no Vercel + Turso como banco de produção
9. `56b6b91` maxDuration 60s
10. `60be73c` histórico embutido como fallback do sync
11. `b7522fa` fonte maickon (GitHub) com 2.994 concursos datados
12. `8eb347e` **Fábrica de números** (gerador avançado, fechamento, termômetro)
