import { useEffect, useState } from 'react'
import { dashboardAPI, reportsAPI } from '@/api'
import { fmt, fmtDate, fmtDateShort, downloadBlob, today, monthStart } from '@/utils'
import { KpiCard, Badge, Avatar, ProgressBar, Spinner, Button } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { PartnerModal } from '@/components/modals'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts'
import {
  TrendingUp, TrendingDown, Wallet, Server,
  Megaphone, Target, AlertCircle, FileDown,
} from 'lucide-react'
import toast from 'react-hot-toast'

const PERIOD_LABELS = { today: 'Сегодня', month: 'Месяц', year: 'Год' }
const CAT_COLORS = ['#534AB7','#1D9E75','#BA7517','#E24B4A','#378ADD','#D4537E','#639922']

// Тепловая карта дохода
function HeatMap({ data }) {
  if (!data || data.length === 0) return null

  const byDate = {}
  data.forEach((d) => { byDate[d.date] = d.amount })
  const max = Math.max(...Object.values(byDate), 1)

  const year = new Date().getFullYear()
  const month = new Date().getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const days = Array.from({ length: daysInMonth }, (_, i) => {
    const d = new Date(year, month, i + 1)
    const key = d.toISOString().slice(0, 10)
    const amount = byDate[key] || 0
    const intensity = max > 0 ? amount / max : 0
    return { day: i + 1, amount, intensity, date: key }
  })

  const getColor = (intensity) => {
    if (intensity === 0) return '#F1EFE8'
    const alpha = 0.15 + intensity * 0.85
    return `rgba(83,74,183,${alpha.toFixed(2)})`
  }

  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(7, 1fr)' }}>
        {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map((d) => (
          <div key={d} className="text-center text-xs text-gray-300 pb-1">{d}</div>
        ))}
        {/* Пустые ячейки до первого числа */}
        {Array.from({ length: (new Date(year, month, 1).getDay() + 6) % 7 }, (_, i) => (
          <div key={'e'+i} />
        ))}
        {days.map(({ day, amount, intensity, date }) => (
          <div
            key={day}
            title={`${fmtDate(date)}: ${fmt(amount)}`}
            className="aspect-square rounded flex items-center justify-center text-xs cursor-default transition-all"
            style={{ background: getColor(intensity), color: intensity > 0.6 ? 'white' : '#534AB7' }}
          >
            {day}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-2 justify-end">
        <span className="text-xs text-gray-400">0</span>
        {[0.15,0.35,0.55,0.75,1].map((v, i) => (
          <div key={i} className="w-4 h-4 rounded" style={{ background: getColor(v) }} />
        ))}
        <span className="text-xs text-gray-400">{fmt(max)}</span>
      </div>
    </div>
  )
}

// Кастомный тултип для recharts
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-3 py-2 text-xs shadow-sm">
      <div className="text-gray-400 mb-1">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>{fmt(p.value)}</div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [period, setPeriod] = useState('month')
  const [partnerModal, setPartnerModal] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)

  useEffect(() => {
    dashboardAPI.get().then((r) => setData(r.data)).catch(() => toast.error('Ошибка загрузки дашборда'))
  }, [])

  const handleReport = async (format) => {
    setReportLoading(true)
    try {
      const dateFrom = monthStart()
      const dateTo = today()
      const fn = format === 'pdf' ? reportsAPI.pdf : reportsAPI.excel
      const res = await fn({ date_from: dateFrom, date_to: dateTo, format })
      downloadBlob(res.data, `report_${dateFrom}_${dateTo}.${format === 'excel' ? 'xlsx' : 'pdf'}`)
    } catch { toast.error('Ошибка генерации отчёта') }
    finally { setReportLoading(false) }
  }

  if (!data) return (
    <div className="flex items-center justify-center h-full">
      <Spinner size={32} />
    </div>
  )

  const kpi = data[period] || data.month

  return (
    <div>
      <PageHeader title="Дашборд" subtitle="Финансовый обзор">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {Object.entries(PERIOD_LABELS).map(([k, v]) => (
            <button
              key={k}
              onClick={() => setPeriod(k)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                period === k ? 'bg-white text-gray-700 shadow-sm' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <Button size="sm" onClick={() => handleReport('pdf')} loading={reportLoading}>
          <FileDown size={13} /> PDF
        </Button>
        <Button size="sm" onClick={() => handleReport('excel')} loading={reportLoading}>
          <FileDown size={13} /> Excel
        </Button>
      </PageHeader>

      <div className="p-5 space-y-4">

        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <KpiCard
            label="Выручка"
            value={fmt(kpi.income)}
            sub={`Среднее: ${fmt(kpi.avg_per_day)}/день`}
            subColor="text-success-600"
          />
          <KpiCard
            label="Расходы"
            value={fmt(kpi.expense)}
            sub={kpi.expense > 0 ? `${Math.round(kpi.expense / kpi.income * 100)}% от выручки` : ''}
            subColor="text-danger-600"
          />
          <KpiCard
            label="Чистая прибыль"
            value={fmt(kpi.profit)}
            sub={kpi.profit >= 0 ? '↑ положительная' : '↓ убыток'}
            subColor={kpi.profit >= 0 ? 'text-success-600' : 'text-danger-600'}
          />
          <KpiCard
            label="Остаток на счёте"
            value={fmt(data.balance)}
            sub={data.servers_warning?.length > 0 ? `⚠ ${data.servers_warning.length} оплат скоро` : 'Всё в порядке'}
            subColor={data.servers_warning?.length > 0 ? 'text-warn-600' : 'text-gray-400'}
          />
          <KpiCard
            label="Лучший день"
            value={kpi.best_day_amount ? fmt(kpi.best_day_amount) : '—'}
            sub={kpi.best_day ? fmtDate(kpi.best_day) : ''}
            subColor="text-primary-600"
          />
        </div>

        {/* Chart + Categories */}
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">График выручки (30 дней)</div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={data.income_chart} margin={{ left: -10 }}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#534AB7" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#534AB7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tickFormatter={fmtDateShort} tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}к` : v} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="amount" stroke="#534AB7" strokeWidth={2} fill="url(#grad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Расходы по категориям</div>
            {data.expense_by_category.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-8">Нет данных</div>
            ) : (
              <div className="space-y-2.5">
                {data.expense_by_category.slice(0, 6).map((c, i) => {
                  const maxAmt = data.expense_by_category[0].amount
                  return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-600 flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: CAT_COLORS[i % CAT_COLORS.length] }} />
                          {c.name}
                        </span>
                        <span className="font-medium">{fmt(c.amount)}</span>
                      </div>
                      <ProgressBar value={c.amount} max={maxAmt} color={CAT_COLORS[i % CAT_COLORS.length]} />
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Heatmap */}
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-500 mb-3">Тепловая карта дохода (текущий месяц)</div>
          <HeatMap data={data.income_chart} />
        </div>

        {/* Partners + Servers + Ads */}
        <div className="grid grid-cols-3 gap-4">

          {/* Partners */}
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Партнёры</div>
            <div className="space-y-1">
              {data.partners_summary.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setPartnerModal(p.id)}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <Avatar name={p.name} color={p.avatar_color} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{p.name}</div>
                    <div className="text-xs text-gray-400">{p.role_label}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-success-600">
                      {p.last_dividend ? fmt(p.last_dividend) : '—'}
                    </div>
                    {p.remaining_debt > 0 && (
                      <div className="text-xs text-warn-600">{fmt(p.remaining_debt)} долг</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Servers */}
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Серверы — оплаты скоро</div>
            {data.servers_warning.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-6">Все в порядке</div>
            ) : (
              <div className="space-y-2">
                {data.servers_warning.map((s) => (
                  <div key={s.id} className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      s.days_until_payment < 0 ? 'bg-danger-600' :
                      s.days_until_payment <= 3 ? 'bg-warn-600' : 'bg-yellow-400'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{s.name}</div>
                      <div className="text-xs text-gray-400 font-mono">{s.ip_address}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-medium text-warn-600">
                        {s.days_until_payment < 0 ? 'Просрочен' : `через ${s.days_until_payment}д`}
                      </div>
                      <div className="text-xs text-gray-400">{s.monthly_cost ? fmt(s.monthly_cost) : ''}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Ads */}
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Реклама за период</div>
            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Потрачено</div>
                <div className="text-base font-medium">{fmt(data.ad_stats.total_spent)}</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-xs text-gray-400 mb-1">Привлечено ПДП</div>
                <div className="text-base font-medium">{data.ad_stats.total_subscribers || '—'}</div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mb-1">Цена 1 подписчика</div>
            <div className="text-xl font-medium text-success-600">
              {data.ad_stats.cost_per_sub ? fmt(data.ad_stats.cost_per_sub) : '—'}
            </div>
            <div className="text-xs text-gray-400 mt-1">{data.ad_stats.campaigns_count} кампаний</div>
          </div>
        </div>

        {/* Milestones */}
        {data.milestones?.length > 0 && (
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Цели</div>
            <div className="grid grid-cols-3 gap-4">
              {data.milestones.map((m) => (
                <div key={m.id}>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="font-medium text-gray-700">{m.title}</span>
                    <span className="text-gray-400">{m.progress_percent}%</span>
                  </div>
                  <ProgressBar value={m.current_amount} max={m.target_amount} color="#534AB7" />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>{fmt(m.current_amount)}</span>
                    <span>{fmt(m.target_amount)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Transactions */}
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-500 mb-3">Последние операции</div>
          <div className="space-y-1">
            {data.recent_transactions.slice(0, 8).map((t) => (
              <div key={t.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <div className={`w-1.5 h-6 rounded-full flex-shrink-0 ${t.type === 'income' ? 'bg-success-600' : 'bg-danger-600'}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{t.description || (t.category?.name || (t.type === 'income' ? 'Доход' : 'Расход'))}</div>
                  <div className="text-xs text-gray-400">{fmtDate(t.date)}</div>
                </div>
                <div className={`text-sm font-medium ${t.type === 'income' ? 'text-success-600' : 'text-danger-600'}`}>
                  {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {partnerModal && (
        <PartnerModal partnerId={partnerModal} onClose={() => setPartnerModal(null)} />
      )}
    </div>
  )
}
