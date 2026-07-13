export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR')
}

export function formatNumber(value, decimals = 2) {
  if (value == null) return '—'
  return value.toLocaleString('pt-BR', { maximumFractionDigits: decimals })
}

export function formatMoney(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value)
}
