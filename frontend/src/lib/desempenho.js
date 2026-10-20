// Desempenho dos jogos salvos agrupado por estratégia — com a régua do acaso.
//
// Uma tabela de médias crua sempre tem um "campeão": com 4 ou 5 estratégias e
// poucas dezenas de jogos, alguma fica no topo por pura flutuação. Por isso
// cada linha traz o intervalo de confiança da diferença para o esperado e um
// veredito que só sai do "indistinguível do acaso" quando o intervalo inteiro
// fica de um lado do zero.
//
// Três cuidados que uma média simples não tem:
//  1. Diferença para o esperado, não média bruta. Um jogo de 8 dezenas faz
//     0,8 acerto em média na Mega; misturado com jogos de 6 ele "ganharia"
//     sem estratégia nenhuma. O esperado e o desvio de cada jogo vêm da
//     conferência do backend (`avaliacao`), que já considera as dezenas dele.
//  2. Jogos do mesmo concurso enfrentam o MESMO sorteio. Dez jogos quase
//     iguais (frequência histórica tende a repetir as quentes) num concurso
//     valem pouco mais que um. O erro-padrão usa o maior entre o teórico
//     (jogos independentes) e o agrupado por concurso (cluster-robusto).
//  3. Várias estratégias comparadas ao mesmo tempo. O intervalo é corrigido
//     por Bonferroni: com k linhas avaliadas, cada uma usa 95%/k de erro, e
//     a chance de ALGUMA aparecer fora do acaso por sorte fica em ≤ 5%.

// Abaixo disto o intervalo ainda é aproximação ruim (a distribuição de
// acertos da Mega é bem assimétrica) e o veredito vira "amostra insuficiente".
export const MIN_CONCURSOS = 30

// Ordem fixa de exibição — deliberadamente NÃO ordenamos pela média, que
// transformaria o card num ranking de ruído.
const ROTULOS = {
  aleatorio: 'Aleatório puro',
  frequencia: 'Frequência histórica',
  atrasados: 'Atrasados',
  balanceado: 'Balanceado',
  avancado: 'Fábrica — avançado',
  'fechamento-reduzida': 'Fechamento reduzido',
  'fechamento-completa': 'Fechamento completo',
}
const ORDEM = [...Object.keys(ROTULOS)]
const SEM_ESTRATEGIA = 'app:sem-estrategia'
const MANUAL = 'manual'

function chaveDe(bet) {
  if (bet.origem === 'manual') return MANUAL
  return bet.estrategia || SEM_ESTRATEGIA
}

export function rotuloEstrategia(chave) {
  if (chave === MANUAL) return 'Suas escolhas (manual)'
  if (chave === SEM_ESTRATEGIA) return 'App (estratégia não registrada)'
  return ROTULOS[chave] ?? chave
}

function posicao(chave) {
  if (chave === MANUAL) return ORDEM.length + 2
  if (chave === SEM_ESTRATEGIA) return ORDEM.length + 1
  const i = ORDEM.indexOf(chave)
  return i === -1 ? ORDEM.length : i
}

// Inversa da normal padrão (Acklam), só a metade superior (p ≥ 0,5) — basta
// para o z crítico. Erro relativo < 1,2e-9.
function probitSuperior(p) {
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239]
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572]
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783]
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416]
  if (p < 0.97575) {
    const q = p - 0.5
    const r = q * q
    return (
      ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )
  }
  const q = Math.sqrt(-2 * Math.log(1 - p))
  return (
    -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
    ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  )
}

// z bicaudal de 95% corrigido para k comparações (k=1 → 1,96; k=4 → 2,50).
export function zCritico(k) {
  return probitSuperior(1 - 0.025 / Math.max(1, k))
}

function comb(n, k) {
  if (k < 0 || k > n) return 0
  let r = 1
  for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i
  return r
}

// P(acertar h) para um jogo de k dezenas: hipergeométrica. Cacheada por k —
// a mesma tabela serve a todos os jogos do mesmo tamanho.
const cacheProb = new Map()
function probAcertos(k, cfg) {
  const chave = `${cfg.code}:${k}`
  if (!cacheProb.has(chave)) {
    const total = comb(cfg.total, cfg.sorteadas)
    const p = []
    for (let h = 0; h <= cfg.sorteadas; h++) {
      p.push((comb(k, h) * comb(cfg.total - k, cfg.sorteadas - h)) / total)
    }
    cacheProb.set(chave, p)
  }
  return cacheProb.get(chave)
}

/* Recebe os jogos, o mapa bet.id -> conferência e a config da loteria;
   devolve uma linha por estratégia com média, esperado, diferença ±
   intervalo, prêmios, veredito e a distribuição de acertos (quantos jogos
   fizeram 0, 1, 2… acertos, e quantos o acaso daria). A média sozinha
   esconde o que paga prêmio: 85 jogos de 1 acerto empatam com poucos jogos
   de 3, e só o segundo caso chega perto da quadra.
   Só entram jogos já conferidos e com a avaliação do backend. */
export function desempenhoPorEstrategia(bets, checks, cfg) {
  const grupos = new Map()
  for (const bet of bets) {
    const c = checks[bet.id]
    if (!c?.encontrado || !c.avaliacao) continue
    const chave = chaveDe(bet)
    if (!grupos.has(chave)) grupos.set(chave, [])
    grupos.get(chave).push({ concurso: bet.concurso, dezenas: bet.dezenas.length, c })
  }

  const linhas = []
  for (const [chave, itens] of grupos) {
    const n = itens.length
    let somaAc = 0
    let somaEsp = 0
    let somaVar = 0
    let premiados = 0
    let premiadosEsp = 0
    let melhor = 0
    const distrib = Array(cfg.sorteadas + 1).fill(0)
    const distribEsperada = Array(cfg.sorteadas + 1).fill(0)
    for (const { dezenas, c } of itens) {
      distrib[c.acertos]++
      probAcertos(dezenas, cfg).forEach((p, h) => {
        distribEsperada[h] += p
      })
      somaAc += c.acertos
      somaEsp += c.avaliacao.esperado
      somaVar += c.avaliacao.desvio ** 2
      if (c.faixa) premiados++
      premiadosEsp += (c.avaliacao.premiado?.pct ?? 0) / 100
      melhor = Math.max(melhor, c.acertos)
    }
    const diferenca = (somaAc - somaEsp) / n

    // Cluster-robusto por concurso: resíduos somados dentro de cada sorteio.
    const porConcurso = new Map()
    for (const { concurso, c } of itens) {
      const r = c.acertos - c.avaliacao.esperado - diferenca
      porConcurso.set(concurso, (porConcurso.get(concurso) ?? 0) + r)
    }
    const g = porConcurso.size
    const varTeorica = somaVar / n ** 2
    let varCluster = 0
    if (g > 1) {
      let s = 0
      for (const v of porConcurso.values()) s += v * v
      varCluster = ((g / (g - 1)) * s) / n ** 2
    }

    linhas.push({
      chave,
      rotulo: rotuloEstrategia(chave),
      jogos: n,
      concursos: g,
      media: somaAc / n,
      esperado: somaEsp / n,
      diferenca,
      erroPadrao: Math.sqrt(Math.max(varTeorica, varCluster)),
      premiados,
      premiadosEsperados: premiadosEsp,
      melhor,
      distrib,
      distribEsperada,
    })
  }

  // Bonferroni sobre as linhas que de fato recebem veredito.
  const avaliadas = linhas.filter((l) => l.concursos >= MIN_CONCURSOS).length
  const z = zCritico(avaliadas)
  for (const l of linhas) {
    l.ic = [l.diferenca - z * l.erroPadrao, l.diferenca + z * l.erroPadrao]
    if (l.concursos < MIN_CONCURSOS) {
      l.nivel = 'insuficiente'
      l.veredito = 'amostra insuficiente'
    } else if (l.ic[0] > 0) {
      l.nivel = 'acima'
      l.veredito = 'acima do acaso'
    } else if (l.ic[1] < 0) {
      l.nivel = 'abaixo'
      l.veredito = 'abaixo do acaso'
    } else {
      l.nivel = 'tipico'
      l.veredito = 'indistinguível do acaso'
    }
  }

  linhas.sort((a, b) => posicao(a.chave) - posicao(b.chave) || a.chave.localeCompare(b.chave))
  return { linhas, z, avaliadas }
}
