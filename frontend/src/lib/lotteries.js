// Registro das loterias no frontend (espelha backend/app/lotteries.py).
// Classes de cor são literais (não interpoladas) para o Tailwind não purgar.

export const LOTERIAS = {
  mega: {
    code: 'mega',
    nome: 'Mega-Sena',
    min: 1,
    max: 60,
    total: 60,
    escolher: 6,
    maxEscolher: 20,
    sorteadas: 6,
    cols: 10,
    preco: 6.0,
    fonte: 'megasena',
    badge: '60',
    blurb: '6 dezenas de 60',
    chance: '1 em 50.063.860 (sena)',
    // Chance de levar QUALQUER faixa premiada com uma aposta simples.
    chanceQualquer: '1 em 2.298',
    avancada: true,
    accent: 'emerald',
    cardClass: 'hover:border-emerald-400',
    badgeClass: 'bg-emerald-600',
    barClass: 'bg-emerald-500',
    rowClass: 'bg-emerald-50/50',
    tintClass: 'bg-emerald-50 border-emerald-200',
    // Faixas premiadas: acertos -> rótulo do prêmio
    premios: [
      { ac: 6, label: 'Sena' },
      { ac: 5, label: 'Quina' },
      { ac: 4, label: 'Quadra' },
    ],
  },
  lofa: {
    code: 'lofa',
    nome: 'Lotofácil',
    min: 1,
    max: 25,
    total: 25,
    escolher: 15,
    maxEscolher: 20,
    sorteadas: 15,
    cols: 5,
    preco: 3.5,
    fonte: 'lotofacil',
    badge: '25',
    blurb: '15 dezenas de 25',
    chance: '1 em 3.268.760 (15 acertos)',
    chanceQualquer: '1 em 9',
    avancada: true,
    accent: 'purple',
    cardClass: 'hover:border-purple-400',
    badgeClass: 'bg-purple-600',
    barClass: 'bg-purple-500',
    rowClass: 'bg-purple-50/50',
    tintClass: 'bg-purple-50 border-purple-200',
    // 11, 12 e 13 acertos têm prêmio FIXO — não dependem do rateio.
    premios: [
      { ac: 15, label: '15 acertos' },
      { ac: 14, label: '14 acertos' },
      { ac: 13, label: '13 acertos · R$ 35 fixo' },
      { ac: 12, label: '12 acertos · R$ 14 fixo' },
      { ac: 11, label: '11 acertos · R$ 7 fixo' },
    ],
  },
}

export const LOTERIA_CODES = Object.keys(LOTERIAS)

export function getLoteria(code) {
  return LOTERIAS[code] || LOTERIAS.mega
}

export function isValidLoteria(code) {
  return code in LOTERIAS
}
