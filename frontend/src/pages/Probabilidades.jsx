import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'
import Card from '../components/Card.jsx'
import Help from '../components/Help.jsx'
import { formatMoney } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'

const fmt = (n) => (n == null ? '—' : n.toLocaleString('pt-BR'))
const pct = (n) => (n == null ? '—' : `${n.toLocaleString('pt-BR')}%`)

/* Barra dupla observado x teórico — o coração da página: as duas curvas
   coincidem, que é como um sorteio honesto se parece. */
function DistBar({ linhas, barClass }) {
  const maxV = Math.max(...linhas.flatMap((l) => [l.observado_pct, l.teorico_pct]), 1)
  return (
    <div className="space-y-1">
      {linhas.map((l) => (
        <div key={l.valor} className="flex items-center gap-2 text-[11px]">
          <span className="w-6 text-right tabular-nums text-zinc-500">{l.valor}</span>
          <div className="flex-1 space-y-0.5">
            <div className="flex items-center gap-1">
              <div
                className={`h-2 rounded-sm ${barClass}`}
                style={{ width: `${(l.observado_pct / maxV) * 100}%` }}
              />
              <span className="tabular-nums text-zinc-600">{l.observado_pct}%</span>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="h-2 bg-zinc-300 rounded-sm"
                style={{ width: `${(l.teorico_pct / maxV) * 100}%` }}
              />
              <span className="tabular-nums text-zinc-400">{l.teorico_pct}%</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Veredito({ cs }) {
  const cor = {
    ok: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    limite: 'bg-amber-50 border-amber-200 text-amber-900',
    atipico: 'bg-amber-50 border-amber-200 text-amber-900',
  }[cs.nivel]
  return (
    <div className={`rounded-lg border px-3 py-2.5 text-sm ${cor}`}>
      <p className="font-semibold">
        Resultado: {cs.veredito} (p = {fmt(cs.p_valor)})
      </p>
      <p className="text-xs mt-1 leading-relaxed">{cs.explicacao}</p>
    </div>
  )
}

export default function Probabilidades() {
  const { cfg } = useLottery()
  const [tabela, setTabela] = useState(null)
  const [alea, setAlea] = useState(null)
  const [erroAlea, setErroAlea] = useState(null)

  useEffect(() => {
    apiGet('/odds/table').then(setTabela).catch(() => setTabela(null))
    apiGet('/stats/aleatoriedade')
      .then(setAlea)
      .catch((e) => setErroAlea(e.message))
  }, [])

  const fixos = tabela?.premios_fixos || {}
  const temFixos = Object.keys(fixos).length > 0
  const rateio = tabela?.rateio || {}

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold">Probabilidades da {cfg.nome}</h2>
        <p className="text-xs text-zinc-500">
          Os números exatos, calculados por matemática — e a verificação, com o histórico real,
          de que não há padrão a explorar.
        </p>
      </div>

      {/* 1. Tabela mestra */}
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Chance por tamanho de aposta
            <Help text="Probabilidade exata de cada faixa, por hipergeométrica. Aumentar as dezenas é a ÚNICA coisa que muda a probabilidade de verdade — e o custo sobe na mesma proporção, porque uma aposta de k dezenas é literalmente C(k,15) apostas simples." />
          </span>
        }
        subtitle={`Aposta simples: ${cfg.escolher} dezenas por ${formatMoney(cfg.preco)}`}
      >
        {tabela ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200">
                  <th className="py-2 pr-3 font-medium">Dezenas</th>
                  <th className="py-2 pr-3 font-medium">Apostas simples</th>
                  <th className="py-2 pr-3 font-medium">Custo</th>
                  {Object.keys(tabela.linhas[0].faixas).map((f) => (
                    <th key={f} className="py-2 pr-3 font-medium">
                      {f}
                    </th>
                  ))}
                  <th className="py-2 font-medium">Ganhar algo</th>
                </tr>
              </thead>
              <tbody>
                {tabela.linhas.map((l) => (
                  <tr
                    key={l.dezenas}
                    className={`border-b border-zinc-100 last:border-0 ${
                      l.dezenas === cfg.escolher ? cfg.rowClass : ''
                    }`}
                  >
                    <td className="py-2 pr-3 font-semibold tabular-nums">{l.dezenas}</td>
                    <td className="py-2 pr-3 tabular-nums text-zinc-600">
                      {fmt(l.combos_simples)}
                    </td>
                    <td className="py-2 pr-3 tabular-nums">{formatMoney(l.custo_estimado)}</td>
                    {Object.values(l.faixas).map((f, i) => (
                      <td key={i} className="py-2 pr-3 tabular-nums text-zinc-600">
                        1 em {fmt(f.one_in)}
                      </td>
                    ))}
                    <td className="py-2 tabular-nums font-semibold">
                      1 em {fmt(l.qualquer.one_in)}
                      <span className="text-xs text-zinc-500 font-normal">
                        {' '}
                        ({fmt(l.qualquer.pct)}%)
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">Carregando…</p>
        )}
        <p className="text-xs text-zinc-500 mt-3 leading-relaxed">
          Não há desconto nem bônus escondido: uma aposta de {cfg.escolher + 3} dezenas dá
          exatamente a mesma chance que comprar aquela quantidade de apostas simples avulsas. O que
          muda é que os bilhetes se sobrepõem — então, quando você acerta, acerta em várias faixas
          de uma vez.
        </p>
      </Card>

      {/* Garantia por casa dos pombos — só existe quando escolher + sorteadas > total */}
      {tabela?.linhas.some((l) => l.garantia_minima.acertos > 0) && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              O que você acerta mesmo no pior caso
              <Help text="Princípio da casa dos pombos: como só existem 25 dezenas e 15 são sorteadas, ao marcar k você deixa 25-k de fora — e no máximo essas podem escapar. O mínimo garantido é k + 15 - 25, sem depender de sorte nenhuma." />
            </span>
          }
          subtitle="Acertos garantidos em qualquer sorteio, sem depender de sorte"
        >
          <div className="flex flex-wrap gap-2">
            {tabela.linhas.map((l) => (
              <div
                key={l.dezenas}
                className={`rounded-lg px-3 py-2 border ${
                  l.garantia_minima.premia ? cfg.tintClass : 'bg-zinc-50 border-zinc-200'
                }`}
              >
                <p className="text-xs text-zinc-500">{l.dezenas} dezenas</p>
                <p className="font-bold tabular-nums">
                  ≥ {l.garantia_minima.acertos} acertos
                </p>
              </div>
            ))}
          </div>
          {!tabela.linhas.some((l) => l.garantia_minima.premia) && (
            <p className="text-sm text-zinc-700 mt-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
              Repare no detalhe: nem a aposta máxima garante prêmio. Com{' '}
              {cfg.maxEscolher} dezenas ({formatMoney(tabela.linhas[tabela.linhas.length - 1].custo_estimado)}
              ) você garante{' '}
              {tabela.linhas[tabela.linhas.length - 1].garantia_minima.acertos} acertos —{' '}
              <strong>exatamente um a menos</strong> que a faixa mínima premiada, que é{' '}
              {Math.min(...cfg.premios.map((p) => p.ac))}. Garantir prêmio exigiria{' '}
              {Math.min(...cfg.premios.map((p) => p.ac)) + (cfg.total - cfg.sorteadas)} dezenas, e a
              Caixa não aceita passar de {cfg.maxEscolher}. O limite do volante está posto
              justamente aí.
            </p>
          )}
        </Card>
      )}

      {/* 2. Prêmios fixos e para onde vai o dinheiro */}
      {temFixos && (
        <Card
          title="O que volta garantido"
          subtitle="Faixas de valor fixo em regulamento — não dependem de rateio nem de quantos ganhadores houve"
        >
          <div className="flex flex-wrap gap-2">
            {Object.entries(fixos).map(([ac, val]) => (
              <div key={ac} className="bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2">
                <p className="text-xs text-zinc-500">{ac} acertos</p>
                <p className="font-bold tabular-nums">{formatMoney(val)}</p>
                <p className="text-[11px] text-zinc-400">
                  {(val / cfg.preco).toLocaleString('pt-BR')}× a aposta
                </p>
              </div>
            ))}
          </div>
          {tabela && (
            <p className={`text-sm text-zinc-700 mt-3 border rounded-lg px-3 py-2 ${cfg.tintClass}`}>
              Em média, <strong>{pct(tabela.linhas[0].retorno_fixo.pct)}</strong> de cada aposta
              volta só por estas faixas fixas — e essa fração é a{' '}
              <strong>mesma para 15 ou para 20 dezenas</strong>, justamente porque a aposta maior é
              só um pacote de apostas simples.
            </p>
          )}
        </Card>
      )}

      {rateio.pool_pct && (
        <Card
          title="Para onde vai o dinheiro apostado"
          subtitle={`${pct(rateio.pool_pct)} da arrecadação volta como prêmio; o restante é repasse social e custeio (Lei 13.756/2018)`}
        >
          <div className="space-y-1.5 text-sm">
            {Object.entries(rateio.faixas || {})
              .sort((a, b) => Number(b[0]) - Number(a[0]))
              .map(([ac, p]) => (
              <div key={ac} className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-zinc-600">{ac} acertos</span>
                <div className="flex-1 bg-zinc-100 rounded h-4 overflow-hidden">
                  <div className={`h-full ${cfg.barClass}`} style={{ width: `${p}%` }} />
                </div>
                <span className="w-12 text-right tabular-nums text-zinc-600">{pct(p)}</span>
                </div>
              ))}
            {Object.entries(rateio.reservas || {}).map(([nome, p]) => (
              <div key={nome} className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-zinc-500 text-xs">{nome}</span>
                <div className="flex-1 bg-zinc-100 rounded h-4 overflow-hidden">
                  <div className="h-full bg-zinc-400" style={{ width: `${p}%` }} />
                </div>
                <span className="w-12 text-right tabular-nums text-zinc-500">{pct(p)}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-zinc-500 mt-3">
            {temFixos
              ? 'Percentuais do que sobra depois de pagas as faixas de prêmio fixo.'
              : 'Percentuais do total destinado à premiação.'}
          </p>
        </Card>
      )}

      {/* 3. O teste de aleatoriedade */}
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Existe padrão? O teste do qui-quadrado
            <Help text="Compara quantas vezes cada dezena saiu com o que o acaso puro produziria. Sob aleatoriedade, o valor esperado da própria estatística é igual aos graus de liberdade — então um resultado perto desse número é a assinatura de um sorteio honesto." />
          </span>
        }
        subtitle={alea ? `Calculado sobre ${fmt(alea.chi_square.draws_considered)} concursos do seu cache` : null}
      >
        {erroAlea && <p className="text-sm text-zinc-500">{erroAlea}</p>}
        {alea && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                ['Qui-quadrado', alea.chi_square.chi2],
                ['Esperado pelo acaso', alea.chi_square.chi2_esperado],
                ['Limite de 5%', alea.chi_square.critico_5pct],
                ['Maior desvio', `${fmt(alea.chi_square.maior_desvio_pct)}%`],
              ].map(([label, v]) => (
                <div key={label} className="bg-zinc-50 rounded-lg p-2.5">
                  <p className="text-[11px] text-zinc-500">{label}</p>
                  <p className="font-bold tabular-nums">{fmt(v)}</p>
                </div>
              ))}
            </div>
            <Veredito cs={alea.chi_square} />
            <div className="grid sm:grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-zinc-500 mb-1">
                  Mais sorteadas (esperado: {alea.chi_square.esperado_pct}%)
                </p>
                {alea.chi_square.mais_frequentes.map((f) => (
                  <div key={f.n} className="flex justify-between tabular-nums text-zinc-600">
                    <span>dezena {String(f.n).padStart(2, '0')}</span>
                    <span>
                      {f.count}× ({f.pct}%)
                    </span>
                  </div>
                ))}
              </div>
              <div>
                <p className="text-zinc-500 mb-1">Menos sorteadas</p>
                {alea.chi_square.menos_frequentes.map((f) => (
                  <div key={f.n} className="flex justify-between tabular-nums text-zinc-600">
                    <span>dezena {String(f.n).padStart(2, '0')}</span>
                    <span>
                      {f.count}× ({f.pct}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <p className="text-xs text-zinc-500 leading-relaxed border-t border-zinc-100 pt-2">
              A dezena que mais saiu está {fmt(alea.chi_square.maior_desvio_pct)}% acima da média —
              e é justamente esse tipo de oscilação que o qui-quadrado acima mede e considera
              normal. Quanto menos dezenas a loteria sorteia por concurso, maior a oscilação
              esperada. Seja qual for o histórico, nenhuma dezena tem probabilidade diferente das
              outras no próximo sorteio.
            </p>
          </div>
        )}
      </Card>

      {/* 4. Observado x teórico */}
      {alea && (
        <Card
          title="Observado × teórico, indicador por indicador"
          subtitle="Colorido = o que aconteceu de verdade · cinza = o que a matemática prevê"
        >
          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-4">
            {alea.indicadores.map((ind) => (
              <div key={ind.chave}>
                <p className="text-sm font-medium">{ind.label}</p>
                <p className="text-[11px] text-zinc-500 mb-1.5">
                  média real {ind.media_observada} · teórica {ind.media_teorica}
                </p>
                <DistBar linhas={ind.linhas} barClass={cfg.barClass} />
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-zinc-100 text-xs text-zinc-600">
            <p className="font-medium">Soma das dezenas</p>
            <p className="text-zinc-500">
              média real {alea.soma.media_observada} · teórica {alea.soma.media_teorica} · desvio
              real {alea.soma.desvio_observado} · teórico {alea.soma.desvio_teorico} · variou de{' '}
              {alea.soma.min} a {alea.soma.max}
            </p>
          </div>
          <p className="text-xs text-zinc-500 mt-3 leading-relaxed">
            As duas curvas se sobrepõem em todos os indicadores. É por isso que os filtros da
            Fábrica são honestamente descritos como cosméticos: eles reproduzem padrões que já são
            os do acaso, e não encontram nenhum viés porque não existe nenhum.
          </p>
        </Card>
      )}
    </div>
  )
}
