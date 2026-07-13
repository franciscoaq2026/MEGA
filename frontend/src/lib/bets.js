// Apostas ficam no navegador (localStorage): sobrevivem a deploys e não
// dependem de banco no servidor (necessário para hospedagem serverless).
// Use exportar/importar backup para trocar de aparelho.

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
  return bet
}

export function removeBet(id) {
  saveBets(loadBets().filter((b) => b.id !== id))
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
  return { importados: merged.length - existing.length, ignorados: data.length - valid.length }
}
