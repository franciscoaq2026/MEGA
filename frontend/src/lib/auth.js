// Login sem senha (magic link) para sincronizar os jogos entre aparelhos.
// A sessão fica no localStorage; o backend valida pelo header X-Session-Id.

const SESSION_KEY = 'megasena.session.v1'

export function getSession() {
  try {
    const raw = JSON.parse(localStorage.getItem(SESSION_KEY))
    return raw && raw.session_id ? raw : null
  } catch {
    return null
  }
}

export function setSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY)
}

export function authHeaders() {
  const s = getSession()
  return s ? { 'X-Session-Id': s.session_id } : {}
}

// Pede um link de acesso por e-mail. Resposta é sempre genérica.
export async function requestLink(email) {
  const res = await fetch('/api/auth/request-link', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  return res.json().catch(() => ({ status: 'error', message: `Erro ${res.status}` }))
}

// Troca o token do magic link por uma sessão. Salva a sessão se der certo.
export async function verifyToken(token) {
  const res = await fetch('/api/auth/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  const data = await res.json().catch(() => ({ status: 'error', message: `Erro ${res.status}` }))
  if (data.status === 'success') {
    setSession({ session_id: data.session_id, email: data.email })
  }
  return data
}

export async function logout() {
  const s = getSession()
  clearSession()
  if (s) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: s.session_id }),
      })
    } catch {
      // ignora falha de rede: a sessão local já foi limpa
    }
  }
}

// Se a URL tiver ?login_token=..., faz o login e limpa o parâmetro.
// Chamado uma vez no start do app (o link do e-mail cai aqui).
export async function consumeLoginTokenFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('login_token')
  if (!token) return null
  let result = null
  try {
    result = await verifyToken(token)
  } catch {
    result = { status: 'error', message: 'Falha ao validar o link.' }
  }
  params.delete('login_token')
  const qs = params.toString()
  const base = window.location.pathname + (qs ? `?${qs}` : '')
  // Após entrar, leva ao hub para escolher a loteria; senão mantém a rota atual.
  const hash = result?.status === 'success' ? '#/' : window.location.hash
  window.history.replaceState({}, '', base + hash)
  return result
}
