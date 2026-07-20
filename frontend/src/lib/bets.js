// Apostas ficam no navegador (localStorage): funcionam offline e sem login.
// Quando o usuário está logado (magic link), são também sincronizadas com a
// nuvem (Turso) para aparecer em qualquer aparelho. A migração dos jogos que
// já estavam no navegador acontece no primeiro sync (nada é perdido).

import { authHeaders, getSession } from './auth.js'

const KEY = 'megasena.bets.v1'

export function loadBets() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY))
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export function saveBets(bets) {
  localStorage.setItem(KEY, JSON.stringify(bets))
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

// Envia as apostas locais e recebe a lista completa da conta (união por id no
// servidor). Espelha o resultado no localStorage. É o que traz os jogos de
// outros aparelhos e migra os jogos locais no primeiro login.
export async function syncBets() {
  if (!getSession()) return loadBets()
  const local = loadBets()
  const res = await fetch('/api/bets/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ bets: local }),
  })
  if (!res.ok) throw new Error(`sync falhou (${res.status})`)
  const data = await res.json()
  const cloud = Array.isArray(data.bets) ? data.bets : []
  saveBets(cloud)
  return cloud
}

// ── API local (síncrona, como antes) + espelho na nuvem ───────────────────────

export function addBet({ concurso, origem, estrategia = null, dezenas }) {
  const bets = loadBets()
  const bet = {
    id: crypto.randomUUID(),
    concurso: Number(concurso),
    origem, // 'manual' | 'app'
    estrategia,
    dezenas: [...dezenas].sort((a, b) => a - b),
    criado_em: new Date().toISOString(),
  }
  bets.push(bet)
  saveBets(bets)
  cloudPost(bet)
  return bet
}

export function removeBet(id) {
  saveBets(loadBets().filter((b) => b.id !== id))
  cloudDelete(id)
}

export function exportBets() {
  const blob = new Blob([JSON.stringify(loadBets(), null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `megasena-jogos-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function importBets(file) {
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
  const existing = loadBets()
  const ids = new Set(existing.map((b) => b.id))
  const merged = [...existing, ...valid.filter((b) => !ids.has(b.id))]
  saveBets(merged)
  // Logado: sobe os importados para a nuvem (e reespelha a lista final).
  if (getSession()) {
    try {
      await syncBets()
    } catch {
      // mantém o merge local mesmo se o sync falhar
    }
  }
  return { importados: merged.length - existing.length, ignorados: data.length - valid.length }
}
