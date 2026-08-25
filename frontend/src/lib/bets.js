// Apostas ficam no navegador (localStorage), separadas por loteria: funcionam
// offline e sem login. Quando o usuário está logado (magic link), são também
// sincronizadas com a nuvem (Turso) para aparecer em qualquer aparelho. A
// migração dos jogos que já estavam no navegador acontece no primeiro sync.

import { authHeaders, getSession } from './auth.js'
import { getLoteria } from './lotteries.js'

// Um jogo só é válido no formato da loteria a que pertence. Vale para o
// backup importado e para o que já está no navegador: o backend recusa o
// LOTE INTEIRO se uma aposta vier fora do formato (422), então uma única
// entrada estragada — um backup da Mega importado dentro da Lotofácil, por
// exemplo — desligava a sincronização em nuvem para sempre, em silêncio.
export function betValida(bet, loteria) {
  const cfg = getLoteria(loteria)
  if (!bet || typeof bet !== 'object') return false
  if (!Number.isInteger(Number(bet.concurso)) || Number(bet.concurso) < 1) return false
  if (bet.origem !== 'manual' && bet.origem !== 'app') return false
  const dz = bet.dezenas
  if (!Array.isArray(dz)) return false
  if (dz.length < cfg.escolher || dz.length > cfg.maxEscolher) return false
  if (new Set(dz).size !== dz.length) return false
  return dz.every((n) => Number.isInteger(n) && n >= cfg.min && n <= cfg.max)
}

// Chave por loteria. A Mega mantém a chave histórica para não perder dados
// de quem já usava o app antes do hub.
function keyFor(loteria = 'mega') {
  return loteria === 'mega' ? 'megasena.bets.v1' : `loterias.bets.${loteria}.v1`
}

// Loterias que saíram do app. Os jogos guardados no navegador são apagados
// uma vez só — o mesmo que o backend faz no banco (db.LOTERIAS_REMOVIDAS).
// Lista explícita de propósito: varrer "toda chave desconhecida" apagaria
// dados de uma loteria que estivesse só temporariamente fora da config.
const LOTERIAS_REMOVIDAS = ['loto'] // Lotomania — substituída pela Lotofácil
const MARCADOR_LIMPEZA = 'loterias.purge.v1'

export function limparLoteriasRemovidas() {
  try {
    const feito = JSON.parse(localStorage.getItem(MARCADOR_LIMPEZA)) || []
    const pendentes = LOTERIAS_REMOVIDAS.filter((c) => !feito.includes(c))
    if (!pendentes.length) return
    for (const code of pendentes) localStorage.removeItem(keyFor(code))
    localStorage.setItem(MARCADOR_LIMPEZA, JSON.stringify([...feito, ...pendentes]))
  } catch {
    // localStorage indisponível (modo privado): nada a fazer
  }
}

export function loadBets(loteria = 'mega') {
  try {
    const raw = JSON.parse(localStorage.getItem(keyFor(loteria)))
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export function saveBets(loteria, bets) {
  localStorage.setItem(keyFor(loteria), JSON.stringify(bets))
}

// ── Sincronização com a nuvem (fire-and-forget: nunca trava a interface) ──────

async function cloudPost(bet) {
  if (!getSession()) return
  try {
    await fetch('/api/bets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(bet),
    })
  } catch {
    // sem rede: o jogo já está salvo localmente e sobe no próximo sync
  }
}

async function cloudDelete(id) {
  if (!getSession()) return
  try {
    await fetch(`/api/bets/${id}`, { method: 'DELETE', headers: authHeaders() })
  } catch {
    // ignora falha de rede
  }
}

// Envia as apostas locais desta loteria e recebe a lista da conta para ela.
export async function syncBets(loteria = 'mega') {
  if (!getSession()) return loadBets(loteria)
  // Só sobem as apostas no formato da loteria: uma entrada inválida faria o
  // servidor recusar o lote inteiro, e nada sincronizaria.
  const local = loadBets(loteria).filter((b) => betValida(b, loteria))
  const res = await fetch(`/api/bets/sync?loteria=${encodeURIComponent(loteria)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ bets: local }),
  })
  if (!res.ok) throw new Error(`sync falhou (${res.status})`)
  const data = await res.json()
  const cloud = Array.isArray(data.bets) ? data.bets : []
  saveBets(loteria, cloud)
  return cloud
}

// ── API local (síncrona) + espelho na nuvem ───────────────────────────────────

// crypto.randomUUID() só existe em contexto seguro (https ou localhost);
// acessando o app pelo IP da rede local ele não existe e o "salvar" quebrava.
function novoId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID()
  return `bet-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export function addBet({ loteria = 'mega', concurso, origem, estrategia = null, dezenas }) {
  const bets = loadBets(loteria)
  const bet = {
    id: novoId(),
    loteria,
    concurso: Number(concurso),
    origem, // 'manual' | 'app'
    estrategia,
    dezenas: [...dezenas].sort((a, b) => a - b),
    criado_em: new Date().toISOString(),
  }
  bets.push(bet)
  saveBets(loteria, bets)
  cloudPost(bet)
  return bet
}

export function removeBet(loteria, id) {
  saveBets(loteria, loadBets(loteria).filter((b) => b.id !== id))
  cloudDelete(id)
}

export function exportBets(loteria = 'mega') {
  const blob = new Blob([JSON.stringify(loadBets(loteria), null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${loteria}-jogos-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function importBets(file, loteria = 'mega') {
  const text = await file.text()
  const data = JSON.parse(text)
  if (!Array.isArray(data)) throw new Error('arquivo inválido: esperado um array de jogos')
  // Antes bastava ter 6 dezenas — o que deixava um backup da Mega entrar na
  // Lotofácil (6 dezenas onde a aposta mínima é 15) e envenenar o sync.
  const valid = data.filter((b) => betValida(b, loteria))
  const existing = loadBets(loteria)
  const ids = new Set(existing.map((b) => b.id))
  // Jogo sem id ganha um: sem isso, vários deles colidiriam em `undefined` e
  // só o primeiro entraria (e nenhum subiria para a nuvem).
  const novos = valid
    .map((b) => ({ ...b, id: b.id || novoId(), loteria }))
    .filter((b) => !ids.has(b.id))
  const merged = [...existing, ...novos]
  saveBets(loteria, merged)
  if (getSession()) {
    try {
      await syncBets(loteria)
    } catch {
      // mantém o merge local mesmo se o sync falhar
    }
  }
  return { importados: merged.length - existing.length, ignorados: data.length - valid.length }
}
