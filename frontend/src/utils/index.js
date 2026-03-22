import { format, parseISO, startOfMonth, endOfMonth, startOfYear } from 'date-fns'
import { ru } from 'date-fns/locale'

export const fmt = (v, decimals = 0) => {
  if (v == null || isNaN(v)) return '—'
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v) + ' ₽'
}

export const fmtNum = (v) => {
  if (v == null || isNaN(v)) return '—'
  return new Intl.NumberFormat('ru-RU').format(v)
}

export const fmtDate = (d) => {
  if (!d) return '—'
  try {
    const date = typeof d === 'string' ? parseISO(d) : d
    return format(date, 'd MMM yyyy', { locale: ru })
  } catch { return d }
}

export const fmtDateShort = (d) => {
  if (!d) return '—'
  try {
    const date = typeof d === 'string' ? parseISO(d) : d
    return format(date, 'd MMM', { locale: ru })
  } catch { return d }
}

export const fmtDateTime = (d) => {
  if (!d) return '—'
  try {
    const date = typeof d === 'string' ? parseISO(d) : d
    return format(date, 'd MMM yyyy HH:mm', { locale: ru })
  } catch { return d }
}

export const toISO = (d) => {
  if (!d) return null
  if (typeof d === 'string') return d.slice(0, 10)
  return format(d, 'yyyy-MM-dd')
}

export const monthStart = () => toISO(startOfMonth(new Date()))
export const monthEnd = () => toISO(endOfMonth(new Date()))
export const yearStart = () => toISO(startOfYear(new Date()))
export const today = () => toISO(new Date())

export const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const ROLE_LABELS = {
  admin: 'Администратор',
  editor: 'Редактор',
  investor: 'Инвестор',
  partner: 'Партнёр',
}

export const TYPE_LABELS = {
  income: 'Доход',
  expense: 'Расход',
}

export const INKAS_LABELS = {
  dividend: 'ДВД',
  return_inv: 'Возврат инвест.',
  investment: 'Вложение',
}

export const MONTH_NAMES = [
  '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

export const clsx = (...args) =>
  args.flat().filter(Boolean).join(' ')
