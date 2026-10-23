import { authHeaders } from './auth.js'

const BASE = '/api'

// Loteria atual — definida pelo LotteryProvider ao entrar em /mega ou /lofa.
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

// O status vai junto no erro: um 401 (sem login) pede outra reação da tela
// do que uma falha de rede.
async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const err = new Error(body?.detail || `Erro ${res.status} na API`)
    err.status = res.status
    throw err
  }
  return res.json()
}

// A sessão segue em toda chamada: gravar resultado (/import-payloads,
// /import-csv) exige login, e os demais endpoints ignoram o header.
export async function apiGet(path) {
  return handle(await fetch(withLoteria(path), { headers: authHeaders() }))
}

export async function apiUpload(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  return handle(await fetch(withLoteria(path), { method: 'POST', headers: authHeaders(), body: fd }))
}

export async function apiPost(path, data) {
  return handle(
    await fetch(withLoteria(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(data),
    }),
  )
}
