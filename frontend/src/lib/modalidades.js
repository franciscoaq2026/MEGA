// Catálogo comparativo de TODAS as modalidades das Loterias Caixa.
//
// Diferente de `lotteries.js` — que descreve apenas as loterias que o app
// realmente opera (gerar jogos, conferir, estatísticas) — este arquivo é
// puramente informativo: situa a Mega-Sena e a Lotofácil (as duas que o site
// tem) dentro do cardápio completo da Caixa. `noSite` marca quais são essas.
//
// Probabilidades: valores publicados pela Caixa para a aposta MÍNIMA de cada
// modalidade. Todas foram reconferidas por cálculo hipergeométrico; onde a
// Caixa arredonda para baixo, mantivemos o número oficial (diferença de ±1).
//
// Preços: tabela vigente após o reajuste de 09/07/2025 (Super Sete em 30/07/2025).

/** Probabilidade de levar QUALQUER faixa de prêmio, somando todas as faixas.
 *
 * Soma as faixas já arredondadas ("1 em 2.332"), então o resultado pode cair
 * 1 unidade abaixo do valor calculado direto da hipergeométrica — na Mega dá
 * 2.297 em vez de 2.298. Onde a diferença é visível na interface, a modalidade
 * declara `qualquerExato` e ele prevalece. */
function somaFaixas(faixas) {
  const p = faixas.reduce((acc, f) => acc + 1 / f.umEm, 0)
  return Math.round(1 / p)
}

const RAW = [
  {
    key: 'mega',
    premioBase: 20000000,
    baseConfirmada: true,
    baseFonte: 'conc. 3030 (11/07), após o 3029 pagar R$ 43 mi',
    nome: 'Mega-Sena',
    noSite: true,
    aposta: '6 dezenas de 60',
    sorteio: 'sorteia 6 dezenas',
    preco: 6.0,
    dias: '3x por semana (ter, qui, sáb)',
    qualquerExato: 2298, // hipergeométrica exata; a soma das faixas dá 2.297
    faixas: [
      { label: 'Sena (6)', umEm: 50063860, principal: true },
      { label: 'Quina (5)', umEm: 154518 },
      { label: 'Quadra (4)', umEm: 2332 },
    ],
    nota: 'O maior prêmio do país e, por consequência, a maior barreira: só 3 faixas premiadas.',
  },
  {
    key: 'milionaria',
    premioBase: 10000000,
    baseConfirmada: true,
    baseFonte: 'mínimo garantido em regulamento (Reserva Garantidora)',
    nome: '+Milionária',
    noSite: false,
    aposta: '6 dezenas de 50 + 2 trevos de 6',
    sorteio: 'sorteia 6 dezenas + 2 trevos',
    preco: 6.0,
    dias: '2x por semana (qua, sáb)',
    faixas: [
      { label: '6 acertos + 2 trevos', umEm: 238360500, principal: true },
      { label: '6 + 1 trevo', umEm: 29795062 },
      { label: '6 + 0 trevo', umEm: 39726750 },
      { label: '5 + 2 trevos', umEm: 902881 },
      { label: '5 + 1', umEm: 112860 },
      { label: '5 + 0', umEm: 150480 },
      { label: '4 + 2', umEm: 16798 },
      { label: '4 + 1', umEm: 2100 },
      { label: '3 + 2', umEm: 900 },
      { label: '2 + 2', umEm: 117 },
    ],
    nota: 'A mais difícil de todas — quase 5x a Mega-Sena — porque os 2 trevos multiplicam por 15.',
  },
  {
    key: 'timemania',
    premioBase: 3200000,
    baseConfirmada: false,
    baseFonte: 'menor valor visto em julho — ainda acumulado',
    nome: 'Timemania',
    noSite: false,
    aposta: '10 dezenas de 80 + Time do Coração',
    sorteio: 'sorteia 7 dezenas + 1 time',
    preco: 3.5,
    dias: '3x por semana (ter, qui, sáb)',
    faixas: [
      { label: '7 acertos', umEm: 26472637, principal: true },
      { label: '6 acertos', umEm: 216103 },
      { label: '5 acertos', umEm: 5220 },
      { label: '4 acertos', umEm: 276 },
      { label: '3 acertos', umEm: 29 },
      { label: 'Time do Coração', umEm: 80 },
    ],
    nota: 'Você marca 10 e só 7 são sorteadas — daí a folga nas faixas baixas.',
  },
  {
    key: 'quina',
    premioBase: 4000000,
    baseConfirmada: false,
    baseFonte: 'menor valor visto em julho — ainda acumulado',
    nome: 'Quina',
    noSite: false,
    aposta: '5 dezenas de 80',
    sorteio: 'sorteia 5 dezenas',
    preco: 3.0,
    dias: '6x por semana (seg a sáb)',
    faixas: [
      { label: 'Quina (5)', umEm: 24040016, principal: true },
      { label: 'Quadra (4)', umEm: 64106 },
      { label: 'Terno (3)', umEm: 866 },
      { label: 'Duque (2)', umEm: 36 },
    ],
    nota: 'Prêmio principal 2x mais provável que a Mega, e o duque (1 em 36) sai com frequência.',
  },
  {
    key: 'lotomania',
    premioBase: 500000,
    baseConfirmada: true,
    baseFonte: '1º concurso após o 2942 pagar',
    nome: 'Lotomania',
    noSite: false,
    aposta: '50 dezenas de 100 (00–99)',
    sorteio: 'sorteia 20 dezenas',
    preco: 3.0,
    dias: '3x por semana (seg, qua, sex)',
    faixas: [
      { label: '20 acertos', umEm: 11372635, principal: true },
      { label: '19 acertos', umEm: 352551 },
      { label: '18 acertos', umEm: 24235 },
      { label: '17 acertos', umEm: 2776 },
      { label: '16 acertos', umEm: 472 },
      { label: '15 acertos', umEm: 112 },
      { label: '0 acertos', umEm: 11372635 },
    ],
    nota: 'Única em que ERRAR TUDO premia: 0 acertos vale tanto quanto 20 e tem a mesma chance.',
  },
  {
    key: 'supersete',
    premioBase: 2700000,
    baseConfirmada: false,
    baseFonte: 'menor valor visto em julho — ainda acumulado',
    nome: 'Super Sete',
    noSite: false,
    aposta: '1 número (0–9) em cada uma das 7 colunas',
    sorteio: 'sorteia 1 número por coluna',
    preco: 3.0,
    dias: '3x por semana (seg, qua, sex)',
    faixas: [
      { label: '7 acertos', umEm: 10000000, principal: true },
      { label: '6 acertos', umEm: 158730 },
      { label: '5 acertos', umEm: 5879 },
      { label: '4 acertos', umEm: 392 },
      { label: '3 acertos', umEm: 44 },
    ],
    nota: 'Não é combinatória: são 7 sorteios independentes de 0 a 9, ou seja, 10⁷ resultados.',
  },
  {
    key: 'duplasena',
    premioBase: 1600000,
    baseConfirmada: false,
    baseFonte: 'menor valor visto em julho — ainda acumulado',
    nome: 'Dupla Sena',
    noSite: false,
    aposta: '6 dezenas de 50',
    sorteio: 'sorteia 6 dezenas DUAS vezes',
    preco: 3.0,
    dias: '3x por semana (ter, qui, sáb)',
    // Faixas já consolidadas: chance de bater a faixa em pelo menos um dos 2 sorteios.
    faixas: [
      { label: 'Sena (6)', umEm: 7945350, principal: true },
      { label: 'Quina (5)', umEm: 30096 },
      { label: 'Quadra (4)', umEm: 560 },
      { label: 'Terno (3)', umEm: 30 },
    ],
    nota: 'Dois sorteios por concurso com o mesmo bilhete — na prática dobra a chance (por sorteio a sena é 1 em 15.890.700).',
  },
  {
    key: 'diadesorte',
    premioBase: 100000,
    baseConfirmada: true,
    baseFonte: 'conc. 1254 (24/07), após o 1253 pagar',
    nome: 'Dia de Sorte',
    noSite: false,
    aposta: '7 dezenas de 31 + 1 Mês de Sorte',
    sorteio: 'sorteia 7 dezenas + 1 mês',
    preco: 2.5,
    dias: '3x por semana (ter, qui, sáb)',
    faixas: [
      { label: '7 acertos', umEm: 2629575, principal: true },
      { label: '6 acertos', umEm: 15652 },
      { label: '5 acertos', umEm: 453 },
      { label: '4 acertos', umEm: 37 },
      { label: 'Mês de Sorte', umEm: 12 },
    ],
    nota: 'A aposta mais barata (R$ 2,50) e o "mês de sorte" premia sozinho — 1 em 12.',
  },
  {
    key: 'lotofacil',
    premioBase: 2000000,
    baseConfirmada: true,
    baseFonte: 'conc. 3744 (24/07), após o 3743 pagar',
    nome: 'Lotofácil',
    noSite: true,
    aposta: '15 dezenas de 25',
    sorteio: 'sorteia 15 dezenas',
    preco: 3.5,
    dias: '6x por semana (seg a sáb)',
    faixas: [
      { label: '15 acertos', umEm: 3268760, principal: true },
      { label: '14 acertos', umEm: 21791 },
      { label: '13 acertos', umEm: 691 },
      { label: '12 acertos', umEm: 59 },
      { label: '11 acertos', umEm: 11 },
    ],
    nota: 'De longe a mais fácil: prêmio principal 15x mais provável que a Mega e 11 acertos sai 1 em ~10.',
  },
  {
    key: 'loteca',
    premioBase: 1000000,
    baseConfirmada: true,
    baseFonte: 'conc. 1263, após o 1262 ter 3 acertadores',
    nome: 'Loteca',
    noSite: false,
    aposta: '1 palpite (1/X/2) em 14 jogos de futebol',
    sorteio: '14 resultados reais',
    preco: 4.0,
    dias: '1x por semana',
    faixas: [
      { label: '14 acertos', umEm: 4782969, principal: true },
      { label: '13 acertos', umEm: 170820 },
    ],
    nota: 'Não é sorteio aleatório: 3¹⁴ combinações, mas o conhecimento de futebol muda a chance real.',
    naoAleatoria: true,
  },
  {
    key: 'federal',
    premioBase: 50000,
    baseConfirmada: true,
    baseFonte: 'prêmio fixo (fração 1/10 de R$ 500 mil) — nunca acumula',
    nome: 'Federal',
    noSite: false,
    aposta: 'fração de bilhete numerado (00000–99999)',
    sorteio: 'sorteia 5 bilhetes',
    // Vendida em bilhete inteiro (R$ 40) ou frações. Usamos a fração de 1/10,
    // que é a compra usual, para ficar comparável às outras apostas mínimas.
    preco: 4.0,
    dias: '2x por semana (qua, sáb)',
    faixas: [
      { label: '1º prêmio', umEm: 100000, principal: true },
      { label: 'qualquer dos 5 prêmios', umEm: 20000 },
    ],
    nota: 'Você não escolhe nada: compra um bilhete pronto. Menor prêmio, mas a melhor chance da Caixa.',
    somaInvalida: true, // as faixas se sobrepõem, não somar
  },
]

/** Modalidades com `qualquer` (chance de levar alguma faixa) e `custoCobertura`. */
export const MODALIDADES = RAW.map((m) => ({
  ...m,
  principal: m.faixas.find((f) => f.principal).umEm,
  qualquer: m.qualquerExato ?? (m.somaInvalida ? m.faixas[1].umEm : somaFaixas(m.faixas)),
  // Quanto custaria comprar todas as combinações do prêmio principal
  custoCobertura: m.preco ? m.faixas.find((f) => f.principal).umEm * m.preco : null,
  // Quanto de cada aposta volta, em média, só pela faixa principal:
  // prêmio na base ÷ chance. É o número que compara modalidades de forma justa,
  // porque normaliza pelo preço e não se deixa inflar por acumulação.
  retorno: m.preco
    ? (100 * (m.premioBase / m.faixas.find((f) => f.principal).umEm)) / m.preco
    : null,
}))

/** Ordenado da mais provável para a menos provável (prêmio principal). */
export const POR_PRINCIPAL = [...MODALIDADES].sort((a, b) => a.principal - b.principal)

/** Ordenado por chance de levar qualquer prêmio. */
export const POR_QUALQUER = [...MODALIDADES].sort((a, b) => a.qualquer - b.qualquer)

/** Ordenado pelo prêmio na base (sem acumulação), do maior para o menor. */
export const POR_PREMIO = [...MODALIDADES].sort((a, b) => b.premioBase - a.premioBase)

/** Ordenado pelo que volta por aposta — a comparação mais justa. */
export const POR_RETORNO = [...MODALIDADES]
  .filter((m) => m.retorno != null)
  .sort((a, b) => b.retorno - a.retorno)

export const ORDENACOES = [
  { id: 'principal', label: 'Chance do prêmio principal', lista: POR_PRINCIPAL },
  { id: 'qualquer', label: 'Chance de ganhar algo', lista: POR_QUALQUER },
  { id: 'premio', label: 'Tamanho do prêmio', lista: POR_PREMIO },
  { id: 'retorno', label: 'Quanto volta por aposta', lista: POR_RETORNO },
]

export const MEGA = MODALIDADES.find((m) => m.key === 'mega')
export const LOTOFACIL = MODALIDADES.find((m) => m.key === 'lotofacil')

/** "1 em 50.063.860" */
export function umEm(n) {
  return `1 em ${n.toLocaleString('pt-BR')}`
}

/** Quantas vezes `m` é mais (ou menos) provável que a referência. */
export function vezesVs(m, ref) {
  const r = ref.principal / m.principal
  if (r >= 1) return { fator: r, mais: true }
  return { fator: 1 / r, mais: false }
}

export function fatorTexto(m, ref) {
  if (m.key === ref.key) return '—'
  const { fator, mais } = vezesVs(m, ref)
  const n = fator >= 10 ? Math.round(fator) : Math.round(fator * 10) / 10
  return `${n.toLocaleString('pt-BR')}× ${mais ? 'mais' : 'menos'} provável`
}
