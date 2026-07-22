// Apostas ficam no navegador (localStorage), separadas por loteria: funcionam
// offline e sem login. Quando o usuário está logado (magic link), são também
// sincronizadas com a nuvem (Turso) para aparecer em qualquer aparelho. A
// migração dos jogos que já estavam no navegador acontece no primeiro sync.

import { authHeaders, getSession } from './auth.js'

// Chave por loteria. A Mega mantém a chave histórica para não perder dados
// de quem já usava o app antes do hub.
function keyFor(loteria = 'mega') {
  return loteria === 'mega' ? 'megasena.bets.v1' : `loterias.bets.${loteria}.v1`
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
  const local = loadBets(loteria)
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

export function addBet({ loteria = 'mega', concurso, origem, estrategia = null, dezenas }) {
  const bets = loadBets(loteria)
  const bet = {
    id: crypto.randomUUID(),
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
  const valid = data.filter(
    (b) =>
      b &&
      typeof b.concurso === 'number' &&
      (b.origem === 'manual' || b.origem === 'app') &&
      Array.isArray(b.dezenas) &&
      b.dezenas.length >= 6,
  )
  const existing = loadBets(loteria)
  const ids = new Set(existing.map((b) => b.id))
  const merged = [...existing, ...valid.filter((b) => !ids.has(b.id)).map((b) => ({ ...b, loteria }))]
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
