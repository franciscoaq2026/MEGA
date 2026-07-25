export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR')
}

export function formatNumber(value, decimals = 2) {
  if (value == null) return '—'
  return value.toLocaleString('pt-BR', { maximumFractionDigits: decimals })
}

// Mostra centavos só quando existem: R$ 3,50 e R$ 2.856,00 saem certos, e
// prêmios redondos (R$ 70.000.000) continuam sem ",00" pendurado.
// Arredondar sempre para inteiro exibia a aposta da Lotofácil como "R$ 4".
export function formatMoney(value) {
  if (value == null) return '—'
  const casas = Number.isInteger(value) ? 0 : 2
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(value)
}
