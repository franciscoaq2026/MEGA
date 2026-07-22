const BASE = '/api'

// Loteria atual — definida pelo LotteryProvider ao entrar em /mega ou /loto.
// É anexada como ?loteria=... em toda chamada. Endpoints que não usam o
// parâmetro simplesmente o ignoram (FastAPI descarta query params extras).
let currentLoteria = 'mega'

export function setApiLoteria(code) {
  currentLoteria = code || 'mega'
}

function withLoteria(path) {
  const sep = path.includes('?') ? '&' : '?'
  return `${BASE}${path}${sep}loteria=${encodeURIComponent(currentLoteria)}`
}

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `Erro ${res.status} na API`)
  }
  return res.json()
}

export async function apiGet(path) {
  return handle(await fetch(withLoteria(path)))
}

export async function apiUpload(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  return handle(await fetch(withLoteria(path), { method: 'POST', body: fd }))
}

export async function apiPost(path, data) {
  return handle(
    await fetch(withLoteria(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  )
}
