import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api.js'
import Card from './Card.jsx'
import { formatMoney } from '../lib/format.js'
import { useLottery } from '../lib/LotteryContext.jsx'

const fmt = (n) => (n == null ? '—' : n.toLocaleString('pt-BR'))

// Chance em %, com casas suficientes para a Mega (0,30%) e sem fingir 100%.
function pctDe(prob) {
  if (prob == null) return '—'
  const v = prob * 100
  if (v > 99.9) return 'mais de 99,9%'
  const casas = v >= 10 ? 1 : v >= 1 ? 2 : 3
  return `${v.toLocaleString('pt-BR', { maximumFractionDigits: casas })}%`
}

// "1 em N": com uma casa quando N é pequeno (1 em 1,1), inteiro acima disso.
function umEm(prob) {
  if (!prob) return '—'
  if (prob > 0.999) return 'quase todo concurso'
  const n = 1 / prob
  return `1 em ${n.toLocaleString('pt-BR', { maximumFractionDigits: n < 20 ? 1 : 0 })}`
}

const SUGESTOES = { mega: [18, 42, 168], lofa: [17.5, 56, 476] }

/* Comparador de mesmo orçamento: o mesmo dinheiro jogado de jeitos
   diferentes. As contas vêm de GET /odds/orcamento; a explicação de como cada
   número sai fica sempre aberta, logo abaixo do quadro. */
export default function CompararOrcamento() {
  const { cfg } = useLottery()
  const sugestoes = SUGESTOES[cfg.code] || [cfg.preco * 5]
  const [valor, setValor] = useState(String(sugestoes[1] ?? sugestoes[0]))
  const [pessoas, setPessoas] = useState(10)
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [busy, setBusy] = useState(false)

  const numero = Number(String(valor).replace(',', '.'))

  useEffect(() => {
    if (!numero || numero <= 0) return undefined
    let vivo = true
    // espera a digitação parar antes de consultar
    const t = setTimeout(() => {
      setBusy(true)
      apiGet(`/odds/orcamento?valor=${numero}&pessoas=${pessoas}`)
        .then((d) => {
          if (!vivo) return
          setDados(d)
          setErro(null)
        })
        .catch((e) => {
          if (!vivo) return
          setDados(null)
          setErro(e.message)
        })
        .finally(() => vivo && setBusy(false))
    }, 350)
    return () => {
      vivo = false
      clearTimeout(t)
    }
  }, [numero, pessoas])

  const opcoes = dados?.opcoes || []
  const maior = Math.max(...opcoes.filter((o) => o.chave !== 'bolao').map((o) => o.qualquer.prob), 0)
  const esp = opcoes.find((o) => o.chave === 'espalhados')
  const mult = opcoes.find((o) => o.chave === 'multipla')

  return (
    <Card
      title="Mesmo dinheiro, jeitos diferentes de jogar"
      subtitle="Digite quanto quer gastar e veja a chance de cada formato, lado a lado"
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-xs text-zinc-500">Quanto quero gastar (R$)</span>
          <input
            type="number"
            min={cfg.preco}
            step={cfg.preco}
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            className="mt-1 w-32 border border-zinc-300 rounded-lg px-2 py-1.5 tabular-nums"
          />
        </label>
        <label className="text-sm">
          <span className="block text-xs text-zinc-500">Pessoas no bolão</span>
          <input
            type="number"
            min="1"
            max="100"
            value={pessoas}
            onChange={(e) => setPessoas(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
            className="mt-1 w-24 border border-zinc-300 rounded-lg px-2 py-1.5 tabular-nums"
          />
        </label>
        <div className="flex flex-wrap gap-1.5">
          {sugestoes.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setValor(String(s))}
              className="px-2.5 py-1.5 rounded-lg border border-zinc-300 text-xs text-zinc-600 hover:bg-zinc-50"
            >
              {formatMoney(s)}
            </button>
          ))}
        </div>
        {busy && <span className="text-xs text-zinc-400 pb-2">Calculando…</span>}
      </div>

      {erro && <p className="text-sm text-amber-800 mt-3">{erro}</p>}

      {dados && (
        <>
          <p className="text-xs text-zinc-500 mt-3">
            {formatMoney(dados.orcamento)} compram <strong>{fmt(dados.jogos_simples)}</strong>{' '}
            {dados.jogos_simples === 1 ? 'aposta simples' : 'apostas simples'} de{' '}
            {formatMoney(dados.preco)}.
          </p>

          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-xs text-zinc-500 border-b border-zinc-200 whitespace-nowrap">
                  <th className="py-2 pr-3 font-medium">Jeito de jogar</th>
                  <th className="py-2 pr-3 font-medium">Você paga</th>
                  <th className="py-2 pr-3 font-medium">Ganhar algum prêmio</th>
                  <th className="py-2 font-medium first-letter:uppercase">{dados.premio_principal}</th>
                </tr>
              </thead>
              <tbody>
                {opcoes.map((o) => {
                  const melhor = o.chave === dados.melhor_ganhar_algo && opcoes.length > 1
                  return (
                    <tr
                      key={o.chave}
                      className={`border-b border-zinc-100 last:border-0 align-top ${
                        melhor ? cfg.rowClass : ''
                      }`}
                    >
                      <td className="py-2 pr-3 min-w-[11rem]">
                        <p className="font-medium">
                          {o.nome}
                          {melhor && (
                            <span
                              className={`block w-fit sm:inline sm:ml-1.5 text-[10px] font-normal text-white rounded px-1.5 py-0.5 ${cfg.badgeClass}`}
                            >
                              mais chance de ganhar algo
                            </span>
                          )}
                        </p>
                        <p className="text-[11px] text-zinc-500 leading-snug">{o.quando_acerta}</p>
                      </td>
                      <td className="py-2 pr-3 tabular-nums whitespace-nowrap">
                        {formatMoney(o.custo)}
                        {o.chave === 'bolao' && (
                          <span className="block text-[11px] text-zinc-500">
                            grupo: {formatMoney(o.custo_grupo)}
                          </span>
                        )}
                        {o.sobra >= 0.01 && (
                          <span className="block text-[11px] text-zinc-500">
                            sobram {formatMoney(o.sobra)}
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3 min-w-[9rem]">
                        <p className="font-semibold tabular-nums">{pctDe(o.qualquer.prob)}</p>
                        {o.chave !== 'bolao' && (
                          <div className="bg-zinc-100 rounded h-1.5 mt-1 overflow-hidden">
                            <div
                              className={`h-full ${cfg.barClass}`}
                              style={{ width: `${maior ? (o.qualquer.prob / maior) * 100 : 0}%` }}
                            />
                          </div>
                        )}
                        <p className="text-[11px] text-zinc-500 tabular-nums mt-0.5">
                          {umEm(o.qualquer.prob)}
                        </p>
                      </td>
                      <td className="py-2 tabular-nums whitespace-nowrap">
                        1 em {fmt(o.principal.one_in)}
                        {o.chave === 'bolao' && (
                          <span className="block text-[11px] text-zinc-500">
                            dividido por {o.pessoas}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {esp && mult && dados.vantagem_sobre_multipla > 1 && (
            <p className={`text-sm text-zinc-700 mt-3 border rounded-lg px-3 py-2 ${cfg.tintClass}`}>
              Com {formatMoney(mult.custo)}, {mult.nome.replace('1 aposta', 'uma aposta')} ganha
              algum prêmio em <strong>{pctDe(mult.qualquer.prob)}</strong> dos concursos; os{' '}
              {fmt(esp.jogos)} jogos simples espalhados ({formatMoney(esp.custo)}), em{' '}
              <strong>{pctDe(esp.qualquer.prob)}</strong>
              . A chance de {dados.premio_principal} é a mesma nos dois.
            </p>
          )}

          <div className="mt-4 pt-3 border-t border-zinc-100">
            <p className="text-sm font-semibold">Como funciona</p>
            <ol className="mt-2 space-y-2 text-xs text-zinc-600 leading-relaxed list-decimal pl-4">
              <li>
                <strong>Quantos jogos o dinheiro compra.</strong> {formatMoney(dados.orcamento)} ÷{' '}
                {formatMoney(dados.preco)} = {fmt(dados.jogos_simples)}{' '}
                {dados.jogos_simples === 1 ? 'aposta simples' : 'apostas simples'} (o troco que não
                completa uma aposta aparece como “sobram”).
              </li>
              <li>
                <strong>Chance de um jogo simples.</strong> Premia quando acerta pelo menos{' '}
                {dados.menor_premio} das {cfg.sorteadas} dezenas sorteadas: {pctDe(dados.p_um_jogo.prob)}{' '}
                ({umEm(dados.p_um_jogo.prob)}). É uma contagem exata de combinações, não estimativa.
              </li>
              <li>
                <strong>Prêmio principal ({dados.premio_principal}): só conta quantas combinações você cobre.</strong>{' '}
                Existem {fmt(dados.universo)} resultados possíveis e cada combinação simples cobre
                um. Chance = combinações cobertas ÷ {fmt(dados.universo)}. Por isso a última coluna
                é igual para qualquer formato que custe o mesmo.
              </li>
              <li>
                <strong>Ganhar algum prêmio: depende de quanto os jogos se repetem.</strong> Jogos
                parecidos premiam juntos, nos mesmos concursos; jogos diferentes premiam em
                concursos diferentes. Quanto menos dezenas em comum, mais concursos com prêmio.
              </li>
              {opcoes.map((o) => (
                <li key={o.chave}>
                  <strong>{o.nome}.</strong> {o.como}
                </li>
              ))}
              <li>
                <strong>O que não muda.</strong> O retorno médio por real apostado é o mesmo em
                todas as linhas: de cada R$ 100 apostados na {dados.nome}, cerca de R${' '}
                {fmt(dados.retorno_pct)} voltam em prêmios. A aposta com mais dezenas ganha menos
                vezes, mas quando ganha leva vários prêmios juntos; os jogos espalhados ganham mais
                vezes, um prêmio de cada vez. Nenhum formato faz o jogo dar lucro em média.
              </li>
            </ol>
          </div>
        </>
      )}
    </Card>
  )
}
