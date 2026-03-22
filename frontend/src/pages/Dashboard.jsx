import { useEffect, useState, useCallback } from 'react'
import { dashboardAPI, reportsAPI, transactionsAPI, paymentsAPI } from '@/api'
import { fmt, fmtDate, fmtDateShort, downloadBlob, today, monthStart, yearStart } from '@/utils'
import { KpiCard, Badge, Avatar, ProgressBar, Spinner, Button, Modal, Input } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { PartnerModal } from '@/components/modals'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { FileDown, Calendar } from 'lucide-react'
import toast from 'react-hot-toast'

const PERIOD_LABELS = { today: 'Сегодня', month: 'Месяц', year: 'Год', custom: 'Период' }
const CAT_COLORS = ['#534AB7','#1D9E75','#BA7517','#E24B4A','#378ADD','#D4537E','#639922']

// ── День: транзакции при клике на тепловую карту ─────────────────────────────
function DayTransactionsModal({ date, onClose }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    transactionsAPI.list({ date_from: date, date_to: date, limit: 100 })
      .then(r => setItems(r.data))
      .finally(() => setLoading(false))
  }, [date])

  const income  = items.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0)
  const expense = items.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0)

  return (
    <Modal open onClose={onClose} title={`Транзакции — ${fmtDate(date)}`} size="md">
      <div className="flex gap-2 mb-4">
        <div className="flex-1 bg-success-50 rounded-xl p-3">
          <div className="text-xs text-success-600 mb-0.5">Доход</div>
          <div className="font-medium text-success-600">{fmt(income)}</div>
        </div>
        <div className="flex-1 bg-danger-50 rounded-xl p-3">
          <div className="text-xs text-danger-600 mb-0.5">Расход</div>
          <div className="font-medium text-danger-600">{fmt(expense)}</div>
        </div>
        <div className="flex-1 bg-gray-50 rounded-xl p-3">
          <div className="text-xs text-gray-500 mb-0.5">Итого</div>
          <div className="font-medium">{fmt(income - expense)}</div>
        </div>
      </div>
      {loading ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : items.length === 0 ? (
        <div className="text-sm text-gray-400 text-center py-6">Нет записей за этот день</div>
      ) : (
        <div className="space-y-0">
          {items.map(t => (
            <div key={t.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
              <div className={`w-1.5 h-5 rounded-full flex-shrink-0 ${t.type === 'income' ? 'bg-success-600' : 'bg-danger-600'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate">{t.description || t.category?.name || (t.type === 'income' ? 'Доход' : 'Расход')}</div>
              </div>
              <div className={`text-sm font-medium ${t.type === 'income' ? 'text-success-600' : 'text-danger-600'}`}>
                {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

// ── Тепловая карта с числами ────────────────────────────────────────────────
function HeatMap({ data, onDayClick }) {
  if (!data || data.length === 0) return (
    <div className="text-xs text-gray-300 text-center py-4">Нет данных</div>
  )

  const byDate = {}
  data.forEach(d => { byDate[d.date] = d.amount })
  const max = Math.max(...Object.values(byDate), 1)

  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const dayOffset = (new Date(year, month, 1).getDay() + 6) % 7

  const days = Array.from({ length: daysInMonth }, (_, i) => {
    const key = new Date(year, month, i + 1).toISOString().slice(0, 10)
    const amount = byDate[key] || 0
    return { day: i + 1, amount, intensity: amount / max, date: key }
  })

  const col = (v) => v === 0 ? '#F1EFE8' : `rgba(83,74,183,${(0.12 + v * 0.88).toFixed(2)})`
  const textCol = (v) => v > 0.55 ? 'rgba(255,255,255,0.9)' : '#888780'

  return (
    <div className="max-w-lg">
      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(7, minmax(0,1fr))' }}>
        {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(d => (
          <div key={d} className="text-center pb-1" style={{ fontSize: '10px', color: '#B4B2A9' }}>{d}</div>
        ))}
        {Array.from({ length: dayOffset }, (_, i) => <div key={'e' + i} />)}
        {days.map(({ day, amount, intensity, date }) => (
          <div
            key={day}
            title={`${date}: ${fmt(amount)}`}
            onClick={() => amount > 0 && onDayClick?.(date)}
            className={`rounded flex items-center justify-center transition-all select-none ${amount > 0 ? 'cursor-pointer hover:ring-1 hover:ring-primary-400' : ''}`}
            style={{
              background: col(intensity),
              aspectRatio: '1',
              fontSize: '10px',
              fontWeight: 500,
              color: textCol(intensity),
              minHeight: '0',
              maxHeight: '32px',
            }}
          >
            {day}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1 mt-2">
        <span style={{ fontSize: '9px', color: '#B4B2A9' }}>меньше</span>
        {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
          <div key={i} className="w-3 h-3 rounded-sm" style={{ background: col(v) }} />
        ))}
        <span style={{ fontSize: '9px', color: '#B4B2A9' }}>больше</span>
      </div>
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-100 rounded-lg px-3 py-2 text-xs shadow-sm">
      <div className="text-gray-400 mb-1">{label}</div>
      <div className="font-medium">{fmt(payload[0].value)}</div>
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [data, setData] = useState(null)
  const [period, setPeriod] = useState('month')
  const [customFrom, setCustomFrom] = useState(monthStart())
  const [customTo, setCustomTo]     = useState(today())
  const [showCustom, setShowCustom] = useState(false)
  const [partnerModal, setPartnerModal] = useState(null)
  const [dayModal, setDayModal]         = useState(null)
  const [reportLoading, setReportLoading] = useState(false)

  const [vpnStats, setVpnStats] = useState(null)

  const load = useCallback(() => {
    dashboardAPI.get().then(r => setData(r.data)).catch(() => toast.error('Ошибка загрузки'))
    paymentsAPI.stats({}).then(r => setVpnStats(r.data)).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])

  const handleReport = async (format) => {
    setReportLoading(true)
    try {
      const from = period === 'today' ? today() : period === 'year' ? yearStart() : period === 'custom' ? customFrom : monthStart()
      const to   = period === 'custom' ? customTo : today()
      const fn   = format === 'pdf' ? reportsAPI.pdf : reportsAPI.excel
      const res  = await fn({ date_from: from, date_to: to, format })
      downloadBlob(res.data, `report_${from}_${to}.${format === 'excel' ? 'xlsx' : 'pdf'}`)
    } catch { toast.error('Ошибка генерации отчёта') }
    finally { setReportLoading(false) }
  }

  if (!data) return (
    <div className="flex items-center justify-center h-full min-h-64"><Spinner size={32} /></div>
  )

  const kpi = data[period === 'custom' ? 'month' : period] || data.month

  return (
    <div>
      <PageHeader title="Дашборд" subtitle="Финансовый обзор">
        <div className="flex gap-0.5 bg-gray-100 rounded-lg p-1">
          {Object.entries(PERIOD_LABELS).map(([k, v]) => (
            <button
              key={k}
              onClick={() => { setPeriod(k); if (k === 'custom') setShowCustom(s => !s); else setShowCustom(false) }}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
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

      {/* Custom date range */}
      {showCustom && (
        <div className="flex gap-3 px-4 py-3 bg-white border-b border-gray-100 items-center flex-wrap">
          <Calendar size={14} className="text-gray-400" />
          <Input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} className="w-36" />
          <span className="text-gray-400 text-sm">—</span>
          <Input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} className="w-36" />
        </div>
      )}

      <div className="p-3 md:p-5 space-y-3 md:space-y-4">

        {/* KPI */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
          <KpiCard label="Выручка" value={fmt(kpi.income)}
            sub={`~${fmt(kpi.avg_per_day)}/день`} subColor="text-success-600" />
          <KpiCard label="Расходы" value={fmt(kpi.expense)}
            sub={kpi.income > 0 ? `${Math.round(kpi.expense / kpi.income * 100)}% от выручки` : ''}
            subColor="text-danger-600" />
          <KpiCard label="Прибыль" value={fmt(kpi.profit)}
            sub={kpi.profit >= 0 ? '↑ положительная' : '↓ убыток'}
            subColor={kpi.profit >= 0 ? 'text-success-600' : 'text-danger-600'} />
          <KpiCard label="Остаток на счёте" value={fmt(data.balance)}
            sub={data.servers_warning?.length > 0 ? `⚠ ${data.servers_warning.length} оплат скоро` : 'Всё в порядке'}
            subColor={data.servers_warning?.length > 0 ? 'text-warn-600' : 'text-gray-400'} />
          <KpiCard label="Лучший день"
            value={kpi.best_day_amount ? fmt(kpi.best_day_amount) : '—'}
            sub={kpi.best_day ? fmtDate(kpi.best_day) : ''} subColor="text-primary-600" />
        </div>

        {/* Chart + Categories */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-2 bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">График выручки (30 дней)</div>
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={data.income_chart} margin={{ left: -10 }}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#534AB7" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#534AB7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tickFormatter={fmtDateShort} tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}к` : v} />
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
              <div className="space-y-2">
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

        {/* Heatmap + VPN stats */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
          <div className="lg:col-span-3 bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Тепловая карта дохода — нажми на день</div>
            <HeatMap data={data.income_chart} onDayClick={date => setDayModal(date)} />
          </div>
          <div className="lg:col-span-2 bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">VPN подписки</div>
            {vpnStats ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-success-50 rounded-xl p-2.5">
                    <div className="text-xs text-success-600 mb-0.5">Активных</div>
                    <div className="text-xl font-semibold text-success-600">{vpnStats.active_subscriptions}</div>
                  </div>
                  <div className={`rounded-xl p-2.5 ${vpnStats.expiring_soon > 0 ? 'bg-warn-50' : 'bg-gray-50'}`}>
                    <div className={`text-xs mb-0.5 ${vpnStats.expiring_soon > 0 ? 'text-warn-600' : 'text-gray-400'}`}>Истекают 3д</div>
                    <div className={`text-xl font-semibold ${vpnStats.expiring_soon > 0 ? 'text-warn-600' : 'text-gray-500'}`}>{vpnStats.expiring_soon}</div>
                  </div>
                </div>
                {vpnStats.plans && vpnStats.plans.length > 0 && (
                  <div className="space-y-1 mt-2">
                    <div className="text-xs text-gray-400 mb-1">По тарифам (активные)</div>
                    {vpnStats.plans.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-primary-400" />
                          <span className="text-gray-600">{p.plan || p.tag || '—'}</span>
                        </span>
                        <span className="font-medium">{p.count} шт</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="pt-2 border-t border-gray-50">
                  <div className="text-xs text-gray-400">Сегодня: <span className="font-medium text-gray-700">{vpnStats.today_count} платежей · {fmt(vpnStats.today_amount)}</span></div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-300 text-center py-6">
                Настройте webhook в разделе<br/><a href="/payments" className="text-primary-400 hover:underline">Платежи</a>
              </div>
            )}
          </div>
        </div>

        {/* Partners + Servers + Ads */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">

          {/* Partners */}
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Партнёры</div>
            <div className="space-y-2">
              {data.partners_summary.map(p => (
                <div
                  key={p.id}
                  onClick={() => setPartnerModal(p.id)}
                  className="p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors border border-gray-50"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar name={p.initials || p.name} color={p.avatar_color} size="sm" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{p.name}</div>
                      <div className="text-xs text-gray-400">{p.role_label}</div>
                    </div>
                    <div className="text-xs font-medium text-success-600">
                      {p.total_dividends ? fmt(p.total_dividends) : '—'}
                    </div>
                  </div>
                  {p.total_invested > 0 && (
                    <div>
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Инвестиции</span>
                        <span className={p.remaining_debt > 0 ? 'text-warn-600' : 'text-success-600'}>
                          {p.remaining_debt > 0 ? `долг ${fmt(p.remaining_debt)}` : '✓ погашено'}
                        </span>
                      </div>
                      <ProgressBar
                        value={p.total_returned}
                        max={p.total_invested}
                        color={p.remaining_debt > 0 ? '#BA7517' : '#1D9E75'}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Servers */}
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Серверы — оплаты скоро</div>
            {data.servers_warning.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-6">Все платежи в порядке</div>
            ) : (
              <div className="space-y-2">
                {data.servers_warning.map(s => (
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
                      {s.monthly_cost && <div className="text-xs text-gray-400">{fmt(s.monthly_cost)}</div>}
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
              <div className="bg-gray-50 rounded-lg p-2.5">
                <div className="text-xs text-gray-400 mb-1">Потрачено</div>
                <div className="text-sm font-medium">{fmt(data.ad_stats.total_spent)}</div>
              </div>
              <div className="bg-gray-50 rounded-lg p-2.5">
                <div className="text-xs text-gray-400 mb-1">Привлечено ПДП</div>
                <div className="text-sm font-medium">{data.ad_stats.total_subscribers || '—'}</div>
              </div>
            </div>
            <div className="text-xs text-gray-400 mb-1">Цена 1 подписчика</div>
            <div className="text-lg font-medium text-success-600">
              {data.ad_stats.cost_per_sub ? fmt(data.ad_stats.cost_per_sub) : '—'}
            </div>
          </div>
        </div>

        {/* Milestones */}
        {data.milestones?.length > 0 && (
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Цели</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.milestones.map(m => (
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

        {/* Recent: Transactions + Payments */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Последние операции</div>
            <div>
              {data.recent_transactions.slice(0, 6).map(t => (
                <div key={t.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                  <div className={`w-1.5 h-5 rounded-full flex-shrink-0 ${t.type === 'income' ? 'bg-success-600' : 'bg-danger-600'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{t.description || t.category?.name || (t.type === 'income' ? 'Доход' : 'Расход')}</div>
                    <div className="text-xs text-gray-400">{fmtDate(t.date)}</div>
                  </div>
                  <div className={`text-sm font-medium whitespace-nowrap ${t.type === 'income' ? 'text-success-600' : 'text-danger-600'}`}>
                    {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-medium text-gray-500">Последние платежи (API)</div>
              <a href="/payments" className="text-xs text-primary-600 hover:underline">все →</a>
            </div>
            {data.recent_payments && data.recent_payments.length > 0 ? (
              <div>
                {data.recent_payments.slice(0, 6).map(p => (
                  <div key={p.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                    <div className="w-1.5 h-5 rounded-full flex-shrink-0 bg-primary-400" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm truncate">{p.plan || p.customer_email || p.customer_id || 'Платёж'}</div>
                      <div className="text-xs text-gray-400">{p.customer_email || p.customer_id || fmtDate(p.date)}</div>
                    </div>
                    <div className="text-sm font-medium text-primary-600 whitespace-nowrap">
                      +{fmt(p.amount)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-300 text-center py-6">
                Платежей через API пока нет.<br/>
                <span className="text-primary-400">Настройте webhook в разделе Платежи</span>
              </div>
            )}
          </div>
        </div>

      </div>

      {partnerModal && (
        <PartnerModal partnerId={partnerModal} onClose={() => setPartnerModal(null)} />
      )}
      {dayModal && (
        <DayTransactionsModal date={dayModal} onClose={() => setDayModal(null)} />
      )}
    </div>
  )
}
