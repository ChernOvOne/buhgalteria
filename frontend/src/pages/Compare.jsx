import { useState, useCallback } from 'react'
import { compareAPI, reportsAPI } from '@/api'
import { fmt, fmtDate, downloadBlob, monthStart, today } from '@/utils'
import { Button, Input, Spinner } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts'
import { TrendingUp, TrendingDown, Minus, Send, FileDown } from 'lucide-react'
import toast from 'react-hot-toast'

const COLOR_A = '#534AB7'
const COLOR_B = '#F59E0B'

// ── Пресеты периодов ──────────────────────────────────────────────────────────
function periodPresets() {
  const t = new Date()
  const y = t.getFullYear()
  const m = t.getMonth()

  const fmt = (d) => d.toISOString().slice(0, 10)
  const firstOfMonth = (year, month) => new Date(year, month, 1)
  const lastOfMonth  = (year, month) => new Date(year, month + 1, 0)

  return [
    {
      label: 'Этот месяц',
      from: fmt(firstOfMonth(y, m)),
      to:   fmt(new Date()),
    },
    {
      label: 'Прошлый месяц',
      from: fmt(firstOfMonth(y, m - 1)),
      to:   fmt(lastOfMonth(y, m - 1)),
    },
    {
      label: 'Этот год',
      from: `${y}-01-01`,
      to:   fmt(new Date()),
    },
    {
      label: 'Прошлый год',
      from: `${y - 1}-01-01`,
      to:   `${y - 1}-12-31`,
    },
    {
      label: 'Q1',
      from: `${y}-01-01`,
      to:   `${y}-03-31`,
    },
    {
      label: 'Q2',
      from: `${y}-04-01`,
      to:   `${y}-06-30`,
    },
  ]
}

// ── Delta badge ───────────────────────────────────────────────────────────────
function Delta({ delta, inverse = false }) {
  if (!delta || delta.pct === null) return null
  const isPositive = inverse ? delta.direction === 'down' : delta.direction === 'up'
  const isNegative = inverse ? delta.direction === 'up' : delta.direction === 'down'

  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium px-1.5 py-0.5 rounded-full ${
      isPositive ? 'bg-success-50 text-success-600' :
      isNegative ? 'bg-danger-50 text-danger-600' :
      'bg-gray-100 text-gray-400'
    }`}>
      {isPositive ? <TrendingUp size={10} /> : isNegative ? <TrendingDown size={10} /> : <Minus size={10} />}
      {delta.pct !== null ? `${delta.pct > 0 ? '+' : ''}${delta.pct}%` : '—'}
    </span>
  )
}

// ── KPI карточка сравнения ────────────────────────────────────────────────────
function KpiCompare({ label, a, b, delta, inverse = false, prefix = '' }) {
  const better = inverse ? b < a : b > a
  const worse  = inverse ? b > a : b < a

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-xs text-gray-400 mb-2">{label}</div>
      <div className="flex items-end gap-3 mb-2">
        <div>
          <div className="text-xs text-gray-400 mb-0.5">A</div>
          <div className="text-base font-semibold" style={{ color: COLOR_A }}>{prefix}{fmt(a)}</div>
        </div>
        <div className="text-gray-300 text-lg pb-0.5">→</div>
        <div>
          <div className="text-xs text-gray-400 mb-0.5">B</div>
          <div className={`text-base font-semibold ${better ? 'text-success-600' : worse ? 'text-danger-600' : 'text-gray-700'}`}>
            {prefix}{fmt(b)}
          </div>
        </div>
      </div>
      <Delta delta={delta} inverse={inverse} />
    </div>
  )
}

// ── Tooltip для графика ───────────────────────────────────────────────────────
function CompareTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-3 py-2 text-xs shadow-sm">
      <div className="text-gray-400 mb-1">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }} className="font-medium">
          {p.name}: {fmt(p.value)}
        </div>
      ))}
    </div>
  )
}

// ── Period Picker ─────────────────────────────────────────────────────────────
function PeriodPicker({ label, color, from, to, onChange }) {
  const presets = periodPresets()

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-3 h-3 rounded-full" style={{ background: color }} />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="flex gap-2 flex-wrap mb-3">
        {presets.map(p => (
          <button
            key={p.label}
            onClick={() => onChange(p.from, p.to)}
            className={`px-2.5 py-1 rounded-full text-xs transition-all ${
              from === p.from && to === p.to
                ? 'text-white font-medium'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            style={from === p.from && to === p.to ? { background: color } : {}}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <Input type="date" value={from} onChange={e => onChange(e.target.value, to)} className="flex-1" />
        <Input type="date" value={to}   onChange={e => onChange(from, e.target.value)} className="flex-1" />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ComparePage() {
  const presets = periodPresets()

  const [aFrom, setAFrom] = useState(presets[1].from)  // прошлый месяц
  const [aTo,   setATo]   = useState(presets[1].to)
  const [bFrom, setBFrom] = useState(presets[0].from)  // этот месяц
  const [bTo,   setBTo]   = useState(presets[0].to)

  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  const handleCompare = useCallback(async () => {
    if (!aFrom || !aTo || !bFrom || !bTo) {
      toast.error('Заполните оба периода')
      return
    }
    setLoading(true)
    try {
      const r = await compareAPI.compare({
        a_from: aFrom, a_to: aTo,
        b_from: bFrom, b_to: bTo,
      })
      setResult(r.data)
    } catch { toast.error('Ошибка загрузки данных') }
    finally { setLoading(false) }
  }, [aFrom, aTo, bFrom, bTo])

  const handleSendTelegram = async () => {
    setSending(true)
    try {
      await compareAPI.sendTelegram({ a_from: aFrom, a_to: aTo, b_from: bFrom, b_to: bTo })
      toast.success('Отчёт отправлен в Telegram!')
    } catch { toast.error('Ошибка отправки') }
    finally { setSending(false) }
  }

  const handlePdf = async (period) => {
    setPdfLoading(true)
    try {
      const [df, dt] = period === 'a' ? [aFrom, aTo] : [bFrom, bTo]
      const res = await reportsAPI.pdf({ date_from: df, date_to: dt, format: 'pdf' })
      downloadBlob(res.data, `compare_${period}_${df}_${dt}.pdf`)
    } catch { toast.error('Ошибка генерации PDF') }
    finally { setPdfLoading(false) }
  }

  // Объединяем графики для recharts
  const chartData = (() => {
    if (!result) return []
    const mapA = Object.fromEntries((result.a.chart || []).map(d => [d.date, d.amount]))
    const mapB = Object.fromEntries((result.b.chart || []).map(d => [d.date, d.amount]))
    const allDates = [...new Set([
      ...Object.keys(mapA),
      ...Object.keys(mapB),
    ])].sort()
    return allDates.map(d => ({
      date: d,
      'Период A': mapA[d] || 0,
      'Период B': mapB[d] || 0,
    }))
  })()

  const catChartData = result
    ? result.cat_compare.slice(0, 8).map(c => ({
        name: c.name.length > 10 ? c.name.slice(0, 10) + '…' : c.name,
        'A': c.a,
        'B': c.b,
        color: c.color,
      }))
    : []

  return (
    <div>
      <PageHeader title="Сравнение периодов" subtitle="Сравните любые два временных промежутка">
        {result && (
          <>
            <Button size="sm" onClick={handleSendTelegram} loading={sending}>
              <Send size={13} /> В Telegram
            </Button>
            <Button size="sm" onClick={() => handlePdf('a')} loading={pdfLoading}>
              <FileDown size={13} /> PDF A
            </Button>
            <Button size="sm" onClick={() => handlePdf('b')} loading={pdfLoading}>
              <FileDown size={13} /> PDF B
            </Button>
          </>
        )}
      </PageHeader>

      <div className="p-3 md:p-5 space-y-4">

        {/* Period pickers */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <PeriodPicker
            label="Период A"
            color={COLOR_A}
            from={aFrom} to={aTo}
            onChange={(f, t) => { setAFrom(f); setATo(t) }}
          />
          <PeriodPicker
            label="Период B"
            color={COLOR_B}
            from={bFrom} to={bTo}
            onChange={(f, t) => { setBFrom(f); setBTo(t) }}
          />
        </div>

        <Button variant="primary" onClick={handleCompare} loading={loading} className="w-full md:w-auto">
          {loading ? 'Загружаем...' : '📊 Сравнить'}
        </Button>

        {loading && (
          <div className="flex justify-center py-16">
            <Spinner size={36} />
          </div>
        )}

        {result && !loading && (
          <>
            {/* KPI Cards */}
            <div>
              <h2 className="text-sm font-medium text-gray-500 mb-3">Ключевые показатели</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiCompare
                  label="Доход" a={result.a.kpi.income} b={result.b.kpi.income}
                  delta={result.deltas.income} />
                <KpiCompare
                  label="Расход" a={result.a.kpi.expense} b={result.b.kpi.expense}
                  delta={result.deltas.expense} inverse />
                <KpiCompare
                  label="Прибыль" a={result.a.kpi.profit} b={result.b.kpi.profit}
                  delta={result.deltas.profit} />
                <KpiCompare
                  label="Среднее в день" a={result.a.kpi.avg_per_day} b={result.b.kpi.avg_per_day}
                  delta={result.deltas.avg_per_day} />
              </div>
            </div>

            {/* Revenue chart */}
            {chartData.length > 0 && (
              <div className="bg-white border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-4">Выручка по дням</div>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={chartData} margin={{ left: -10 }}>
                    <defs>
                      <linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={COLOR_A} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={COLOR_A} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gB" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={COLOR_B} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={COLOR_B} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false}
                      tickFormatter={d => d.slice(5)} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false}
                      tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}к` : v} />
                    <Tooltip content={<CompareTooltip />} />
                    <Legend />
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1EFE8" />
                    <Area type="monotone" dataKey="Период A" stroke={COLOR_A} strokeWidth={2} fill="url(#gA)" dot={false} />
                    <Area type="monotone" dataKey="Период B" stroke={COLOR_B} strokeWidth={2} fill="url(#gB)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Expense by category */}
            {catChartData.length > 0 && (
              <div className="bg-white border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-4">Расходы по категориям</div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={catChartData} margin={{ left: -10 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false}
                      tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}к` : v} />
                    <Tooltip content={<CompareTooltip />} />
                    <Legend />
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1EFE8" />
                    <Bar dataKey="A" fill={COLOR_A} radius={[3,3,0,0]} maxBarSize={32} />
                    <Bar dataKey="B" fill={COLOR_B} radius={[3,3,0,0]} maxBarSize={32} />
                  </BarChart>
                </ResponsiveContainer>

                {/* Таблица категорий */}
                <div className="mt-4 space-y-1">
                  {result.cat_compare.map((c, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-0">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: c.color }} />
                      <span className="text-sm text-gray-600 flex-1">{c.name}</span>
                      <span className="text-sm font-medium w-28 text-right" style={{ color: COLOR_A }}>{fmt(c.a)}</span>
                      <span className="text-sm font-medium w-28 text-right" style={{ color: COLOR_B }}>{fmt(c.b)}</span>
                      <span className="w-20 text-right">
                        <Delta delta={c.delta} inverse />
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Payments + Ads + Inkas */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

              {/* Платежи VPN */}
              <div className="bg-white border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-3">💳 Платежи VPN</div>
                <div className="space-y-2">
                  {[
                    { label: 'Выручка',    a: result.a.payments.amount,  b: result.b.payments.amount },
                    { label: 'Кол-во',     a: result.a.payments.count,   b: result.b.payments.count, noFmt: true },
                  ].map((row, i) => (
                    <div key={i} className="flex justify-between text-sm border-b border-gray-50 pb-1.5">
                      <span className="text-gray-400">{row.label}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: COLOR_A }}>{row.noFmt ? row.a : fmt(row.a)}</span>
                        <span className="text-gray-300">→</span>
                        <span style={{ color: COLOR_B }} className="font-medium">
                          {row.noFmt ? row.b : fmt(row.b)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {/* По тарифам */}
                  {(result.a.payments.by_tag?.length > 0 || result.b.payments.by_tag?.length > 0) && (
                    <div className="pt-1">
                      <div className="text-xs text-gray-400 mb-1">По тарифам</div>
                      {[...new Set([
                        ...(result.a.payments.by_tag || []).map(t => t.plan || t.tag),
                        ...(result.b.payments.by_tag || []).map(t => t.plan || t.tag),
                      ])].map(plan => {
                        const pa = (result.a.payments.by_tag || []).find(t => (t.plan || t.tag) === plan)
                        const pb = (result.b.payments.by_tag || []).find(t => (t.plan || t.tag) === plan)
                        return (
                          <div key={plan} className="flex justify-between text-xs py-0.5">
                            <span className="text-gray-500">{plan || '—'}</span>
                            <span>
                              <span style={{ color: COLOR_A }}>{pa?.count || 0}</span>
                              <span className="text-gray-300 mx-1">→</span>
                              <span style={{ color: COLOR_B }} className="font-medium">{pb?.count || 0}</span>
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Реклама */}
              <div className="bg-white border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-3">📢 Реклама</div>
                <div className="space-y-2">
                  {[
                    { label: 'Потрачено',   a: result.a.ads.spend,        b: result.b.ads.spend },
                    { label: 'ПДП',         a: result.a.ads.subscribers,  b: result.b.ads.subscribers, noFmt: true },
                    { label: 'Кампаний',    a: result.a.ads.count,        b: result.b.ads.count, noFmt: true },
                    { label: '₽/ПДП',      a: result.a.ads.cost_per_sub || 0, b: result.b.ads.cost_per_sub || 0 },
                  ].map((row, i) => (
                    <div key={i} className="flex justify-between text-sm border-b border-gray-50 pb-1.5">
                      <span className="text-gray-400">{row.label}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: COLOR_A }}>{row.noFmt ? row.a : fmt(row.a)}</span>
                        <span className="text-gray-300">→</span>
                        <span style={{ color: COLOR_B }} className="font-medium">
                          {row.noFmt ? row.b : fmt(row.b)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Инкас */}
              <div className="bg-white border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-3">💸 Инкас</div>
                <div className="space-y-2">
                  {[
                    { label: 'Дивиденды',  a: result.a.inkas.total_dvd, b: result.b.inkas.total_dvd },
                    { label: 'Возврат',    a: result.a.inkas.total_ret, b: result.b.inkas.total_ret },
                    { label: 'Итого',      a: result.a.inkas.total_dvd + result.a.inkas.total_ret,
                                           b: result.b.inkas.total_dvd + result.b.inkas.total_ret },
                  ].map((row, i) => (
                    <div key={i} className={`flex justify-between text-sm pb-1.5 ${i < 2 ? 'border-b border-gray-50' : 'font-medium pt-1'}`}>
                      <span className={i === 2 ? 'text-gray-700' : 'text-gray-400'}>{row.label}</span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: COLOR_A }}>{fmt(row.a)}</span>
                        <span className="text-gray-300">→</span>
                        <span style={{ color: COLOR_B }}>{fmt(row.b)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Итоговая оценка */}
            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <div className="text-sm font-medium mb-3">🏆 Итоговая оценка</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Доход',   delta: result.deltas.income,    better: 'up' },
                  { label: 'Расход',  delta: result.deltas.expense,   better: 'down' },
                  { label: 'Прибыль', delta: result.deltas.profit,    better: 'up' },
                  { label: 'Ср. день',delta: result.deltas.avg_per_day, better: 'up' },
                ].map((item, i) => {
                  const win = item.delta?.direction === item.better
                  const lose = item.delta && item.delta.direction !== 'neutral' && item.delta.direction !== item.better
                  return (
                    <div key={i} className={`rounded-xl p-3 text-center ${
                      win ? 'bg-success-50' : lose ? 'bg-danger-50' : 'bg-gray-50'
                    }`}>
                      <div className={`text-2xl mb-1 ${win ? '' : lose ? '' : ''}`}>
                        {win ? '✅' : lose ? '❌' : '➡️'}
                      </div>
                      <div className="text-xs font-medium text-gray-600">{item.label}</div>
                      <div className={`text-xs mt-0.5 ${win ? 'text-success-600' : lose ? 'text-danger-600' : 'text-gray-400'}`}>
                        Период B {win ? 'лучше' : lose ? 'хуже' : 'равно'}
                        {item.delta?.pct !== null && item.delta?.pct !== undefined
                          ? ` на ${Math.abs(item.delta.pct)}%` : ''}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

          </>
        )}
      </div>
    </div>
  )
}
