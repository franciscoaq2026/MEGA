import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MODALIDADES, ORDENACOES } from '../lib/modalidades.js'
import { LOTERIAS } from '../lib/lotteries.js'

const fmt = (n) => (n == null ? '—' : n.toLocaleString('pt-BR'))

function dinheiro(v) {
  if (v == null) return '—'
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toLocaleString('pt-BR')} mi`
  return `R$ ${v.toLocaleString('pt-BR')}`
}

/** Código no app (mega/lofa) da modalidade, quando ela está no site. */
const NO_APP = { mega: 'mega', lotofacil: 'lofa' }

function Linha({ m, destaque }) {
  const code = NO_APP[m.key]
  return (
    <tr className={`border-b border-zinc-100 last:border-0 ${m.noSite ? 'bg-emerald-50/40' : ''}`}>
      <td className="py-2 pr-3">
        {code ? (
          <Link to={`/${code}`} className="font-medium underline decoration-zinc-300">
            {m.nome}
          </Link>
        ) : (
          <span className="font-medium text-zinc-700">{m.nome}</span>
        )}
        {m.noSite && (
          <span className="ml-1.5 text-[10px] bg-emerald-600 text-white rounded px-1 py-0.5 align-middle">
            no site
          </span>
        )}
        <span className="block text-[11px] text-zinc-500">{m.aposta}</span>
      </td>
      <td className={`py-2 pr-3 tabular-nums ${destaque === 'principal' ? 'font-bold' : ''}`}>
        1 em {fmt(m.principal)}
      </td>
      <td className={`py-2 pr-3 tabular-nums ${destaque === 'qualquer' ? 'font-bold' : ''}`}>
        1 em {fmt(m.qualquer)}
      </td>
      <td className={`py-2 pr-3 tabular-nums ${destaque === 'premio' ? 'font-bold' : ''}`}>
        {!m.baseConfirmada && <span className="text-amber-600" title={m.baseFonte}>≤ </span>}
        {dinheiro(m.premioBase)}
      </td>
      <td className="py-2 pr-3 tabular-nums text-zinc-600">
        {m.preco ? `R$ ${m.preco.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '—'}
      </td>
      <td className={`py-2 tabular-nums ${destaque === 'retorno' ? 'font-bold' : ''}`}>
        {m.retorno == null
          ? '—'
          : `${!m.baseConfirmada ? '≤ ' : ''}${m.retorno.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`}
      </td>
    </tr>
  )
}

export default function Comparar() {
  const [ordem, setOrdem] = useState('retorno')
  const atual = ORDENACOES.find((o) => o.id === ordem)
  const naoConfirmadas = MODALIDADES.filter((m) => m.premioBase && !m.baseConfirmada)

  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 flex flex-col">
      <header className="bg-white border-b border-zinc-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-3">
          <Link to="/" className="text-zinc-400 hover:text-zinc-700 text-sm" title="Voltar">
            ←
          </Link>
          <div>
            <h1 className="font-bold text-lg">As 11 modalidades da Caixa</h1>
            <p className="text-xs text-zinc-500">
              probabilidade, prêmio e quanto volta — para situar as duas que este site opera
            </p>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto px-4 py-6 space-y-4">
        {/* Ordenação: cada critério conta uma história diferente */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-4">
          <p className="text-sm font-semibold mb-2">Ordenar por</p>
          <div className="flex flex-wrap gap-2">
            {ORDENACOES.map((o) => (
              <button
                key={o.id}
                onClick={() => setOrdem(o.id)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  ordem === o.id
                    ? 'border-emerald-600 bg-emerald-600 text-white font-medium'
                    : 'border-zinc-300 text-zinc-600 hover:border-emerald-400'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200">
                  <th className="py-2 pr-3 font-medium">Modalidade</th>
                  <th className="py-2 pr-3 font-medium">Prêmio principal</th>
                  <th className="py-2 pr-3 font-medium">Ganhar algo</th>
                  <th className="py-2 pr-3 font-medium">Prêmio na base</th>
                  <th className="py-2 pr-3 font-medium">Aposta</th>
                  <th className="py-2 font-medium">Volta por aposta</th>
                </tr>
              </thead>
              <tbody>
                {atual.lista.map((m) => (
                  <Linha key={m.key} m={m} destaque={ordem} />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* A leitura que a tabela sozinha não entrega */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-5 space-y-3 text-sm">
          <p className="font-semibold">Como ler isto</p>
          <p className="text-zinc-600 leading-relaxed">
            <strong>Prêmio na base</strong> é o valor logo depois de alguém ganhar, sem acumulação.
            É o único jeito justo de comparar: um prêmio acumulado não é uma oportunidade, é o
            retrato de vários concursos seguidos sem ninguém acertar.
          </p>
          <p className="text-zinc-600 leading-relaxed">
            <strong>Volta por aposta</strong> = prêmio na base ÷ chance ÷ preço. Normaliza tudo e é
            a coluna que mais aproxima as modalidades de uma comparação honesta. Nenhuma fica
            positiva: por lei, a fatia que retorna como prêmio é fixa (~43% a 46%) e igual para
            todas. O que muda é o <em>formato</em> do pagamento, nunca o total.
          </p>
          <div className="bg-zinc-50 rounded-lg p-3 text-zinc-700 leading-relaxed">
            Ordene por <strong>chance do prêmio principal</strong> e depois por{' '}
            <strong>tamanho do prêmio</strong>: as duas listas saem quase invertidas. Quanto mais
            fácil ganhar, menor o prêmio — sem exceção. A Lotofácil é a que menos obedece a essa
            regra, e foi por isso que ela entrou no site.
          </div>
        </div>

        {/* Honestidade sobre a qualidade do dado */}
        {naoConfirmadas.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-xs text-amber-900 leading-relaxed">
            <p className="font-semibold mb-1">Sobre os valores marcados com “≤”</p>
            <p>
              Em {naoConfirmadas.map((m) => m.nome).join(', ')} não localizei o concurso exato em
              que o prêmio voltou à base. O valor mostrado é o menor observado em julho de 2026, que
              já estava parcialmente acumulado — então a base real é <strong>mais baixa</strong> e o
              retorno delas é <strong>pior</strong> do que a tabela indica. Estão sendo favorecidas.
            </p>
          </div>
        )}

        <div className="bg-white border border-zinc-200 rounded-2xl p-5">
          <p className="font-semibold text-sm mb-2">As duas que este site opera</p>
          <div className="grid sm:grid-cols-2 gap-3">
            {Object.values(LOTERIAS).map((l) => (
              <Link
                key={l.code}
                to={`/${l.code}`}
                className={`border border-zinc-200 rounded-xl p-3 transition-colors ${l.cardClass}`}
              >
                <p className="font-medium">{l.nome}</p>
                <p className="text-xs text-zinc-500">{l.blurb}</p>
                <p className="text-xs text-zinc-600 mt-1">
                  {l.chance} · ganhar algo {l.chanceQualquer}
                </p>
              </Link>
            ))}
          </div>
        </div>

        <p className="text-xs text-zinc-500">
          Probabilidades calculadas por hipergeométrica e conferidas com os valores publicados pela
          Caixa. Preços da tabela vigente após o reajuste de 09/07/2025. Prêmios de base levantados
          em 24/07/2026 — eles mudam a cada concurso, então valem como ordem de grandeza.
        </p>
      </main>
    </div>
  )
}
