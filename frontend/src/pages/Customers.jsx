import { useEffect, useState, useCallback } from 'react'
import { customersAPI } from '@/api'
import { fmt, fmtDate, fmtDateTime } from '@/utils'
import { Button, Input, Modal, Table, Tr, Td, Badge, Empty, Spinner, KpiCard } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Search, User, ExternalLink, X } from 'lucide-react'
import toast from 'react-hot-toast'

// ── Customer Detail Modal ────────────────────────────────────────────────────
function CustomerModal({ customerId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    customersAPI.get(customerId)
      .then(r => setData(r.data))
      .catch(() => toast.error('Ошибка загрузки'))
      .finally(() => setLoading(false))
  }, [customerId])

  if (loading) return (
    <Modal open onClose={onClose} title="Клиент" size="lg">
      <div className="flex justify-center py-12"><Spinner /></div>
    </Modal>
  )
  if (!data) return null

  return (
    <Modal open onClose={onClose} title={data.full_name || data.telegram_username || `ID ${data.telegram_id}`} size="lg">
      <div className="space-y-4">
        {/* Info grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Telegram ID</div>
            <div className="text-sm font-mono">{data.telegram_id}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Username</div>
            <div className="text-sm">@{data.telegram_username || '—'}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Источник</div>
            <div className="text-sm">{data.utm_campaign || data.utm_code || data.source || 'Прямой'}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Первый визит</div>
            <div className="text-sm">{fmtDate(data.first_seen_at)}</div>
          </div>
        </div>

        {/* Financial stats */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-success-50 rounded-xl p-3">
            <div className="text-xs text-success-600 mb-1">LTV</div>
            <div className="text-lg font-medium text-success-600">{fmt(data.total_paid)}</div>
          </div>
          <div className="bg-primary-50 rounded-xl p-3">
            <div className="text-xs text-primary-600 mb-1">Платежей</div>
            <div className="text-lg font-medium text-primary-600">{data.payments_count}</div>
          </div>
          <div className={`rounded-xl p-3 ${data.subscription_end && new Date(data.subscription_end) >= new Date() ? 'bg-success-50' : 'bg-danger-50'}`}>
            <div className={`text-xs mb-1 ${data.subscription_end && new Date(data.subscription_end) >= new Date() ? 'text-success-600' : 'text-danger-600'}`}>Подписка</div>
            <div className={`text-sm font-medium ${data.subscription_end && new Date(data.subscription_end) >= new Date() ? 'text-success-600' : 'text-danger-600'}`}>
              {data.subscription_end ? (new Date(data.subscription_end) >= new Date() ? `до ${fmtDate(data.subscription_end)}` : 'Истекла') : '—'}
            </div>
          </div>
        </div>

        {/* Current plan */}
        {data.current_plan && (
          <div className="bg-primary-50 border border-primary-100 rounded-xl p-3">
            <div className="text-xs text-primary-600 mb-1">Текущий тариф</div>
            <div className="text-sm font-medium text-primary-600">{data.current_plan}</div>
          </div>
        )}

        {/* Payment history */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">История платежей</div>
          {data.payments && data.payments.length > 0 ? (
            <div className="space-y-0">
              {data.payments.map(p => (
                <div key={p.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                  <div className="w-1.5 h-5 rounded-full flex-shrink-0 bg-success-600" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{p.plan || 'Платёж'}</div>
                    <div className="text-xs text-gray-400">{fmtDate(p.date)}</div>
                  </div>
                  <div className="text-sm font-medium text-success-600">+{fmt(p.amount)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-gray-400 text-center py-4">Платежей пока нет</div>
          )}
        </div>
      </div>
    </Modal>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function CustomersPage() {
  const [customers, setCustomers] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [filter, setFilter] = useState('all') // all | paid | free

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      if (filter === 'paid') params.has_paid = true
      if (filter === 'free') params.has_paid = false
      const [custRes, statsRes] = await Promise.all([
        customersAPI.list(params),
        customersAPI.stats(),
      ])
      setCustomers(custRes.data)
      setStats(statsRes.data)
    } catch { toast.error('Ошибка загрузки') }
    finally { setLoading(false) }
  }, [search, filter])

  useEffect(() => { load() }, [load])

  return (
    <div>
      <PageHeader title="Клиенты" subtitle="База клиентов VPN-сервиса" />

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 p-3 md:p-5 pb-0">
          <KpiCard label="Всего клиентов" value={stats.total_customers} sub={`+${stats.new_this_week} за неделю`} subColor="text-success-600" />
          <KpiCard label="Оплатили" value={stats.paid_customers} sub={`Конверсия ${stats.conversion_rate}%`} subColor="text-primary-600" />
          <KpiCard label="Средний LTV" value={fmt(stats.avg_ltv)} sub={`Активных ${stats.active_subscriptions}`} subColor="text-success-600" />
          <KpiCard label="Retention" value={`${stats.retention_rate}%`}
            sub={`Churn ${stats.churn_rate}%`}
            subColor={stats.retention_rate >= 50 ? 'text-success-600' : 'text-warn-600'} />
        </div>
      )}

      {/* Search & filters */}
      <div className="flex gap-2 p-3 md:p-5 pb-0 flex-wrap items-end">
        <div className="flex-1 min-w-48">
          <Input
            placeholder="Поиск по имени, username, telegram ID..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {[
            { key: 'all', label: 'Все' },
            { key: 'paid', label: 'Платящие' },
            { key: 'free', label: 'Бесплатные' },
          ].map(f => (
            <button key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                filter === f.key ? 'bg-white text-gray-700 shadow-sm' : 'text-gray-400 hover:text-gray-600'
              }`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-3 md:p-5">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : customers.length === 0 ? (
          <Empty text="Клиенты не найдены" />
        ) : (
          <>
            {/* Mobile cards */}
            <div className="md:hidden space-y-2">
              {customers.map(c => (
                <div key={c.id} onClick={() => setSelectedId(c.id)}
                  className="bg-white border border-gray-100 rounded-xl p-3 cursor-pointer hover:bg-gray-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center bg-primary-50 text-primary-600 text-sm font-medium flex-shrink-0">
                      {(c.full_name || c.telegram_username || '?')[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{c.full_name || `@${c.telegram_username}` || c.telegram_id}</div>
                      <div className="text-xs text-gray-400">{c.current_plan || 'Нет подписки'}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-success-600">{c.payments_count > 0 ? fmt(c.total_paid) : '—'}</div>
                      <div className="text-xs text-gray-400">{c.payments_count} опл.</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop table */}
            <div className="hidden md:block bg-white border border-gray-100 rounded-xl overflow-hidden">
              <Table headers={['Клиент', 'Telegram ID', 'Источник', 'Тариф', 'LTV', 'Платежей', 'Подписка']}>
                {customers.map(c => (
                  <Tr key={c.id} onClick={() => setSelectedId(c.id)} className="cursor-pointer">
                    <Td>
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-primary-50 text-primary-600 text-xs font-medium flex-shrink-0">
                          {(c.full_name || c.telegram_username || '?')[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="text-sm font-medium">{c.full_name || '—'}</div>
                          <div className="text-xs text-gray-400">@{c.telegram_username || '—'}</div>
                        </div>
                      </div>
                    </Td>
                    <Td className="font-mono text-xs text-gray-500">{c.telegram_id}</Td>
                    <Td>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                        c.source === 'leadtex' ? 'bg-primary-50 text-primary-600' :
                        c.utm_code ? 'bg-warn-50 text-warn-600' :
                        'bg-gray-100 text-gray-500'
                      }`}>
                        {c.utm_code || c.source || 'direct'}
                      </span>
                    </Td>
                    <Td className="text-sm">{c.current_plan || '—'}</Td>
                    <Td className="font-medium text-success-600">{c.payments_count > 0 ? fmt(c.total_paid) : '—'}</Td>
                    <Td className="text-center">{c.payments_count}</Td>
                    <Td>
                      {c.subscription_end ? (
                        <Badge variant={new Date(c.subscription_end) >= new Date() ? 'success' : 'danger'}>
                          {new Date(c.subscription_end) >= new Date() ? `до ${fmtDate(c.subscription_end)}` : 'Истекла'}
                        </Badge>
                      ) : '—'}
                    </Td>
                  </Tr>
                ))}
              </Table>
            </div>
          </>
        )}
      </div>

      {selectedId && (
        <CustomerModal customerId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
