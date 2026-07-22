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
    badge: '60',
    blurb: '6 dezenas de 60',
    chance: '1 em 50.063.860 (sena)',
    avancada: true,
    accent: 'emerald',
    cardClass: 'hover:border-emerald-400',
    badgeClass: 'bg-emerald-600',
  },
  loto: {
    code: 'loto',
    nome: 'Lotomania',
    min: 0,
    max: 99,
    total: 100,
    escolher: 50,
    maxEscolher: 50,
    sorteadas: 20,
    cols: 10,
    badge: '100',
    blurb: '50 dezenas de 100',
    chance: '1 em 11.372.635 (20 ou 0 acertos)',
    avancada: false,
    accent: 'indigo',
    cardClass: 'hover:border-indigo-400',
    badgeClass: 'bg-indigo-600',
  },
}

export const LOTERIA_CODES = Object.keys(LOTERIAS)

export function getLoteria(code) {
  return LOTERIAS[code] || LOTERIAS.mega
}

export function isValidLoteria(code) {
  return code in LOTERIAS
}
