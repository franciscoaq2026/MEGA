const BASE = '/api'

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail || `Erro ${res.status} na API`)
  }
  return res.json()
}

export async function apiGet(path) {
  return handle(await fetch(`${BASE}${path}`))
}

export async function apiUpload(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  return handle(await fetch(`${BASE}${path}`, { method: 'POST', body: fd }))
}

export async function apiPost(path, data) {
  return handle(
    await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  )
}
