// Sincronização dos sorteios, em duas fases. Usada pelo botão em Sorteios e,
// em segundo plano, ao abrir o app (Layout).
//
// 1. Servidor (/sync): histórico embutido + espelhos no GitHub, em lotes. Não
//    precisa de login e cobre tudo até a última rodada dos espelhos, que são
//    atualizados todo dia a partir da Caixa.
// 2. Navegador: busca na Caixa (ou na guidi) o que o servidor ainda não tem e
//    repassa ao /import-payloads, que confere e grava. É o que traz o
//    resultado minutos depois do sorteio, com data e prêmio do próximo
//    concurso. Gravar exige login: sem sessão, esta fase é pulada.

import { apiGet, apiPost } from './api.js'
import { getSession } from './auth.js'

// Avisa as telas abertas (Início, Sorteios, Meus jogos) que entrou resultado.
export const EVENTO_SORTEIOS = 'sorteios-atualizados'

// Fontes oficiais acessadas DIRETO do navegador do usuário. A Caixa recusa o
// IP do servidor (Vercel) e a guidi só aceita IPs do Brasil, mas as duas
// respondem ao navegador de quem usa o site — então os concursos mais novos
// entram por aqui. As URLs dependem do "slug" da loteria (megasena, lotofacil).
function fontesDiretas(fonte) {
  return [
    {
      nome: 'Caixa',
      url: (n) =>
        n
          ? `https://servicebus2.caixa.gov.br/portaldeloterias/api/${fonte}/${n}`
          : `https://servicebus2.caixa.gov.br/portaldeloterias/api/${fonte}`,
    },
    {
      nome: 'guidi',
      url: (n) =>
        n
          ? `https://api.guidi.dev.br/loteria/${fonte}/${n}`
          : `https://api.guidi.dev.br/loteria/${fonte}/ultimo`,
    },
  ]
}

async function fetchDireto(url) {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), 12000)
  try {
    const res = await fetch(url, { signal: ctl.signal, headers: { Accept: 'application/json' } })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } finally {
    clearTimeout(t)
  }
}

// Busca do navegador os concursos que faltam depois do último salvo e envia
// os payloads brutos ao backend (/import-payloads), que valida e grava.
async function sincronizarPeloNavegador(ultimoLocal, onProgress, fontes) {
  for (const fonte of fontes) {
    try {
      const ultimo = await fetchDireto(fonte.url())
      const numUltimo = Number(ultimo.numero ?? ultimo.concurso)
      if (!Number.isFinite(numUltimo) || numUltimo <= ultimoLocal) {
        // Já estamos em dia — mas reenvia o último resultado assim mesmo, para
        // o backend atualizar o "próximo concurso" (data e prêmio estimado
        // vêm no payload do último sorteio).
        if (Number.isFinite(numUltimo)) {
          try {
            await apiPost('/import-payloads', { payloads: [ultimo] })
          } catch (e) {
            if (e.status === 401) throw e
            // outro erro: só a atualização do "próximo" não aconteceu
          }
        }
        return { fonte: fonte.nome, enviados: 0, atualRemoto: numUltimo || ultimoLocal }
      }
      const faltando = []
      for (let n = ultimoLocal + 1; n < numUltimo; n++) faltando.push(n)
      const alvoTotal = faltando.length + 1

      let payloads = [ultimo]
      let enviados = 0
      const flush = async () => {
        if (!payloads.length) return
        const r = await apiPost('/import-payloads', { payloads })
        enviados += r.added
        payloads = []
        onProgress(enviados, alvoTotal)
      }

      for (let i = 0; i < faltando.length; i += 10) {
        const lote = faltando.slice(i, i + 10)
        const res = await Promise.allSettled(lote.map((n) => fetchDireto(fonte.url(n))))
        payloads.push(...res.filter((r) => r.status === 'fulfilled').map((r) => r.value))
        if (payloads.length >= 25) await flush()
      }
      await flush()
      return { fonte: fonte.nome, enviados, atualRemoto: numUltimo }
    } catch (e) {
      // Sessão recusada: trocar de fonte não resolve, quem chama decide.
      if (e.status === 401) throw e
      // CORS ou rede: tenta a próxima fonte; se todas falharem, retorna null
    }
  }
  return null
}

// Roda as duas fases. onProgress recebe { added, remaining, fase }.
// Devolve { servidor, direto, travou, avisos, semLogin }:
// - servidor: concursos gravados pela fase 1;
// - direto: resultado da fase 2 ({ fonte, enviados, atualRemoto }) ou null;
// - travou: a fase 1 parou sem progresso com concursos ainda faltando;
// - avisos: avisos do servidor sobre os espelhos;
// - semLogin: a fase 2 não rodou por falta de sessão válida.
export async function sincronizarSorteios(cfg, onProgress = () => {}) {
  // O laço para em três situações: acabou (remaining 0), o lote não gravou
  // nada (added 0 — repetir só repetiria o mesmo pedido) ou o teto de
  // rodadas, folga sobre o maior histórico (3.810 ÷ 200 = 20 lotes).
  let servidor = 0
  let travou = false
  let avisos = []
  for (let volta = 0; volta < 60; volta++) {
    const r = await apiPost('/sync')
    servidor += r.added
    avisos = r.errors ?? []
    onProgress({ added: servidor, remaining: r.remaining, fase: 'servidor' })
    if (r.remaining <= 0) break
    if (r.added === 0) {
      travou = true
      break
    }
  }

  if (!getSession()) return { servidor, direto: null, travou, avisos, semLogin: true }

  const st = await apiGet('/status')
  const ultimoLocal = st.ultimo_local?.concurso ?? 0
  let direto = null
  if (ultimoLocal > 0) {
    onProgress({ added: servidor, remaining: 0, fase: 'navegador' })
    try {
      direto = await sincronizarPeloNavegador(
        ultimoLocal,
        (env, alvo) =>
          onProgress({ added: servidor + env, remaining: Math.max(alvo - env, 0), fase: 'navegador' }),
        fontesDiretas(cfg.fonte),
      )
    } catch (e) {
      if (e.status !== 401) throw e
      return { servidor, direto: null, travou, avisos, semLogin: true }
    }
  }
  return { servidor, direto, travou, avisos, semLogin: false }
}

// Ao abrir o app: sincroniza em segundo plano, no máximo a cada 20 minutos
// por loteria, sem mensagem nenhuma — o botão em Sorteios continua
// disponível e mostra os erros. Se algo mudou, dispara EVENTO_SORTEIOS para
// as telas abertas recarregarem.
const INTERVALO_AUTO_MS = 20 * 60 * 1000
let autoRodando = false

export async function sincronizarEmSegundoPlano(cfg) {
  if (autoRodando) return
  const chave = `sorteios.autosync.v1.${cfg.code}`
  try {
    if (Date.now() - Number(localStorage.getItem(chave) || 0) < INTERVALO_AUTO_MS) return
    localStorage.setItem(chave, String(Date.now()))
  } catch {
    // sem localStorage (modo privado): sincroniza assim mesmo
  }
  autoRodando = true
  try {
    const r = await sincronizarSorteios(cfg)
    // `direto` também conta: mesmo sem concurso novo, a data e o prêmio do
    // próximo concurso podem ter mudado.
    if (r.servidor > 0 || r.direto) {
      window.dispatchEvent(new CustomEvent(EVENTO_SORTEIOS, { detail: { loteria: cfg.code } }))
    }
  } catch {
    // silencioso de propósito
  } finally {
    autoRodando = false
  }
}
