import { useEffect, useState, useCallback } from 'react'
import { paymentsAPI } from '@/api'
import { fmt, fmtDate, fmtDateTime, today, monthStart } from '@/utils'
import { Button, Input, Modal, Table, Tr, Td, Badge, Empty, Spinner, KpiCard } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Trash2, Copy, Eye, AlertCircle, CheckCircle, Clock, Filter } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const PLAN_COLORS = {
  '1m': 'info', '3m': 'success', '6m': 'warn', '12m': 'income',
}

const SUB_FILTERS = [
  { label: 'Все',          value: '' },
  { label: 'Активные',     value: 'active' },
  { label: 'Истекают',     value: 'expiring_soon' },
  { label: 'Истекли',      value: 'expired' },
  { label: 'Без подписки', value: 'no_sub' },
]

function PaymentDetailModal({ paymentId, onClose }) {
  const [p, setP] = useState(null)
  useEffect(() => { paymentsAPI.get(paymentId).then(r => setP(r.data)) }, [paymentId])

  if (!p) return <Modal open onClose={onClose} title="Платёж"><div className="flex justify-center py-8"><Spinner /></div></Modal>

  const isExpired = p.sub_end && new Date(p.sub_end) < new Date()
  const isExpiringSoon = p.sub_end && !isExpired && (new Date(p.sub_end) - new Date()) < 3 * 86400000

  return (
    <Modal open onClose={onClose} title={`Платёж — ${fmt(p.amount)}`} size="md">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-success-50 rounded-xl p-3">
            <div className="text-xs text-success-600 mb-1">Сумма</div>
            <div className="text-lg font-medium text-success-600">{fmt(p.amount)}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Тариф</div>
            <div className="text-sm font-medium">{p.plan || '—'}</div>
          </div>
        </div>
        <div className="space-y-2 text-sm">
          {[
            ['Клиент', p.customer_name || '—'],
            ['Email', p.customer_email || '—'],
            ['Telegram ID', p.customer_id || '—'],
            ['Источник', p.source || '—'],
            ['Внешний ID', p.external_id || '—'],
            ['Дата оплаты', fmtDate(p.date)],
            ['Создано', p.created_at ? fmtDateTime(p.created_at) : '—'],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-gray-50 pb-2">
              <span className="text-gray-400">{k}</span>
              <span className="font-medium text-right max-w-48 truncate">{v}</span>
            </div>
          ))}
        </div>
        {(p.sub_start || p.sub_end) && (
          <div className={`p-3 rounded-xl border ${isExpired ? 'bg-danger-50 border-danger-100' : isExpiringSoon ? 'bg-warn-50 border-warn-100' : 'bg-success-50 border-success-100'}`}>
            <div className="flex items-center gap-2 text-sm">
              {isExpired ? <AlertCircle size={14} className="text-danger-600" /> : isExpiringSoon ? <Clock size={14} className="text-warn-600" /> : <CheckCircle size={14} className="text-success-600" />}
              <span className={isExpired ? 'text-danger-600' : isExpiringSoon ? 'text-warn-600' : 'text-success-600'}>
                {isExpired ? 'Подписка истекла' : isExpiringSoon ? 'Истекает скоро' : 'Подписка активна'}
              </span>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {p.sub_start && `Начало: ${fmtDate(p.sub_start)}`}{p.sub_start && p.sub_end && ' · '}{p.sub_end && `Конец: ${fmtDate(p.sub_end)}`}
            </div>
          </div>
        )}
        {p.raw_data && (
          <details className="text-xs">
            <summary className="text-gray-400 cursor-pointer hover:text-gray-600">Исходный JSON</summary>
            <pre className="bg-gray-50 rounded-lg p-3 mt-2 overflow-auto max-h-48 text-xs font-mono">{JSON.stringify(p.raw_data, null, 2)}</pre>
          </details>
        )}
      </div>
    </Modal>
  )
}

export default function PaymentsPage() {
  const [payments, setPayments] = useState([])
  const [stats, setStats]       = useState(null)
  const [keys, setKeys]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [tab, setTab]           = useState('payments')
  const [detailId, setDetailId] = useState(null)
  const [newKeyName, setNewKeyName] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const { isAdmin } = useAuthStore()

  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo]     = useState(today())
  const [search, setSearch]     = useState('')
  const [subStatus, setSubStatus] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [expiringDays, setExpiringDays] = useState(3)

  const loadPayments = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        date_from: dateFrom, date_to: dateTo,
        ...(search && { search }),
        ...(subStatus && { subscription_status: subStatus }),
        ...(planFilter && { plan_tag: planFilter }),
        expiring_days: expiringDays,
      }
      const [pRes, sRes] = await Promise.all([
        paymentsAPI.list(params),
        paymentsAPI.stats({ date_from: dateFrom, date_to: dateTo }),
      ])
      setPayments(pRes.data)
      setStats(sRes.data)
    } catch { toast.error('Ошибка загрузки') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo, search, subStatus, planFilter, expiringDays])

  const loadKeys = useCallback(async () => {
    if (isAdmin()) { try { const r = await paymentsAPI.listKeys(); setKeys(r.data) } catch {} }
  }, [])

  useEffect(() => { loadPayments() }, [loadPayments])
  useEffect(() => { loadKeys() }, [loadKeys])

  const handleDeletePayment = async (id) => {
    if (!confirm('Удалить платёж и связанный доход?')) return
    await paymentsAPI.delete(id); toast.success('Удалено'); loadPayments()
  }
  const handleCreateKey = async (e) => {
    e.preventDefault(); if (!newKeyName) return
    await paymentsAPI.createKey({ name: newKeyName }); toast.success('Ключ создан'); setNewKeyName(''); loadKeys()
  }
  const handleDeleteKey = async (id) => {
    if (!confirm('Отозвать ключ?')) return
    await paymentsAPI.deleteKey(id); toast.success('Ключ отозван'); loadKeys()
  }
  const copyText = (text) => { navigator.clipboard?.writeText(text); toast.success('Скопировано') }

  const getSubBadge = (p) => {
    if (!p.sub_end) return null
    const isExpired = new Date(p.sub_end) < new Date()
    const isExpiringSoon = !isExpired && (new Date(p.sub_end) - new Date()) < 3 * 86400000
    if (isExpired) return <Badge variant="danger">Истекла</Badge>
    if (isExpiringSoon) return <Badge variant="warn">Истекает {fmtDate(p.sub_end)}</Badge>
    return <Badge variant="success">до {fmtDate(p.sub_end)}</Badge>
  }

  // Уникальный ключ для каждого тарифа: tag+plan чтобы не было коллизий
  const getPlanKey = (p) => `${p.tag || ''}|${p.plan || ''}`
  const activeFiltersCount = [search, subStatus, planFilter].filter(Boolean).length

  return (
    <div>
      <PageHeader title="Платежи" subtitle="Входящие оплаты через API">
        <Button size="sm" variant={showFilters ? 'primary' : 'default'} onClick={() => setShowFilters(!showFilters)}>
          <Filter size={13} /> Фильтры
          {activeFiltersCount > 0 && <span className="w-4 h-4 rounded-full bg-primary-600 text-white text-xs flex items-center justify-center">{activeFiltersCount}</span>}
        </Button>
      </PageHeader>

      <div className="flex gap-0 border-b border-gray-100 bg-white px-4">
        {[['payments','Платежи'],['keys','API ключи']].map(([k,v]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-3 text-sm transition-all ${tab===k ? 'text-primary-600 border-b-2 border-primary-600 font-medium' : 'text-gray-400 hover:text-gray-600'}`}>{v}</button>
        ))}
      </div>

      {tab === 'payments' && (
        <div>
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 p-3 md:p-5 pb-0">
              <KpiCard label="За период" value={fmt(stats.total_amount)} sub={`${stats.total_count} платежей`} subColor="text-gray-400" />
              <KpiCard label="Сегодня" value={fmt(stats.today_amount)} sub={`${stats.today_count} платежей`} subColor="text-success-600" />
              <KpiCard label="Активных подписок" value={stats.active_subscriptions} sub="пользователей" subColor="text-primary-600" />
              <KpiCard label="Истекают 3 дня" value={stats.expiring_soon}
                sub={stats.expiring_soon > 0 ? 'требуют внимания' : 'всё в порядке'}
                subColor={stats.expiring_soon > 0 ? 'text-warn-600' : 'text-gray-400'} />
            </div>
          )}

          {/* Plan filter buttons — каждый тариф имеет уникальный ключ */}
          {stats?.plans?.length > 0 && (
            <div className="px-3 md:px-5 pt-3 pb-0">
              <div className="flex gap-2 flex-wrap">
                <button onClick={() => setPlanFilter('')}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${!planFilter ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
                  Все тарифы
                </button>
                {stats.plans.map((p, idx) => {
                  const key = getPlanKey(p)
                  return (
                    <button key={idx} onClick={() => setPlanFilter(planFilter === key ? '' : key)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                        planFilter === key ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}>
                      {p.plan || p.tag || '—'} · {p.count}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          <div className={`px-3 md:px-5 pt-3 space-y-3 ${showFilters ? '' : 'hidden md:block'}`}>
            <div className="flex gap-2 flex-wrap items-end">
              <Input type="date" label="От" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-36" />
              <Input type="date" label="До" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-36" />
              <div className="flex-1 min-w-48">
                <Input placeholder="Поиск по имени, email, ID..." value={search} onChange={e => setSearch(e.target.value)} />
              </div>
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {SUB_FILTERS.map(opt => (
                <button key={opt.value} onClick={() => setSubStatus(opt.value)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${subStatus === opt.value ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
                  {opt.label}
                </button>
              ))}
              {subStatus === 'expiring_soon' && (
                <div className="flex items-center gap-1.5 ml-2">
                  <span className="text-xs text-gray-400">через</span>
                  {[3, 7, 14, 30].map(d => (
                    <button key={d} onClick={() => setExpiringDays(d)}
                      className={`px-2 py-0.5 rounded-full text-xs ${expiringDays === d ? 'bg-warn-600 text-white' : 'bg-gray-100 text-gray-500'}`}>{d}д</button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="p-3 md:p-5">
            {loading ? <div className="flex justify-center py-12"><Spinner /></div>
            : payments.length === 0 ? <Empty text="Платежей не найдено" />
            : (
              <>
                <div className="md:hidden space-y-2">
                  {payments.map(p => (
                    <div key={p.id} onClick={() => setDetailId(p.id)}
                      className="bg-white border border-gray-100 rounded-xl p-3 cursor-pointer hover:bg-gray-50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-1.5 self-stretch rounded-full flex-shrink-0 bg-success-600" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium truncate">{p.customer_name || p.customer_id || 'Платёж'}</span>
                            <span className="text-sm font-medium text-success-600 flex-shrink-0 ml-2">+{fmt(p.amount)}</span>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs text-gray-400">{fmtDate(p.date)}</span>
                            {p.plan && <Badge variant={PLAN_COLORS[p.plan_tag] || 'info'}>{p.plan}</Badge>}
                            {getSubBadge(p)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="hidden md:block bg-white border border-gray-100 rounded-xl overflow-hidden">
                  <Table headers={['Дата','Клиент','Тариф','Подписка','Сумма','']}>
                    {payments.map(p => (
                      <Tr key={p.id} onClick={() => setDetailId(p.id)} className="cursor-pointer group">
                        <Td className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(p.date)}</Td>
                        <Td>
                          <div className="text-sm font-medium">{p.customer_name || p.customer_id || '—'}</div>
                          {p.customer_email && <div className="text-xs text-gray-400">{p.customer_email}</div>}
                        </Td>
                        <Td>{p.plan ? <Badge variant={PLAN_COLORS[p.plan_tag] || 'info'}>{p.plan}</Badge> : '—'}</Td>
                        <Td>{getSubBadge(p) || '—'}</Td>
                        <Td className="font-medium text-success-600">+{fmt(p.amount)}</Td>
                        <Td>
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={e => { e.stopPropagation(); setDetailId(p.id) }} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"><Eye size={12} /></button>
                            {isAdmin() && <button onClick={e => { e.stopPropagation(); handleDeletePayment(p.id) }} className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600"><Trash2 size={12} /></button>}
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </Table>
                </div>
                <div className="text-xs text-gray-400 mt-3 text-center">Показано {payments.length} платежей</div>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'keys' && isAdmin() && (
        <div className="p-3 md:p-5 space-y-4">
          <form onSubmit={handleCreateKey} className="flex gap-3 flex-wrap">
            <Input placeholder="Название ключа (например: Бот VPN)" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} className="flex-1 min-w-48" />
            <Button type="submit" variant="primary"><Plus size={13} /> Создать ключ</Button>
          </form>

          {keys.length === 0 ? <Empty text="Нет API ключей — создайте первый для приёма платежей" />
          : (
            <>
              <div className="md:hidden space-y-2">
                {keys.map(k => (
                  <div key={k.id} className="bg-white border border-gray-100 rounded-xl p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">{k.name}</span>
                      <span className="text-xs text-gray-400">{k.request_count || 0} запросов</span>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <code className="text-xs font-mono bg-gray-50 px-2 py-1 rounded flex-1 truncate select-all">{k.key}</code>
                      <button onClick={() => copyText(k.key)} className="p-1.5 rounded hover:bg-primary-50 text-gray-400 hover:text-primary-600 flex-shrink-0"><Copy size={12} /></button>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">{k.last_used ? `Использовался: ${fmtDateTime(k.last_used)}` : 'Не использовался'}</span>
                      <button onClick={() => handleDeleteKey(k.id)} className="text-xs text-danger-600 hover:underline">Отозвать</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="hidden md:block bg-white border border-gray-100 rounded-xl overflow-hidden">
                <Table headers={['Название','Ключ','Запросов','Последнее использование','']}>
                  {keys.map(k => (
                    <Tr key={k.id} className="group">
                      <Td className="font-medium">{k.name}</Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <code className="text-xs font-mono bg-gray-50 px-2 py-0.5 rounded max-w-48 truncate select-all">{k.key}</code>
                          <button onClick={() => copyText(k.key)} className="p-1.5 rounded hover:bg-primary-50 hover:text-primary-600 text-gray-400 flex-shrink-0"><Copy size={12} /></button>
                        </div>
                      </Td>
                      <Td className="text-gray-500">{k.request_count || 0}</Td>
                      <Td className="text-xs text-gray-400">{k.last_used ? fmtDateTime(k.last_used) : 'Не использовался'}</Td>
                      <Td><button onClick={() => handleDeleteKey(k.id)} className="p-1.5 rounded opacity-0 group-hover:opacity-100 hover:bg-danger-50 text-gray-400 hover:text-danger-600"><Trash2 size={12} /></button></Td>
                    </Tr>
                  ))}
                </Table>
              </div>
            </>
          )}

          <div className="bg-primary-50 border border-primary-100 rounded-xl p-4 text-sm">
            <div className="font-medium text-primary-600 mb-2">Webhook URL</div>
            <div className="flex items-center gap-2 bg-white rounded-lg p-2 border border-primary-100">
              <code className="text-xs font-mono flex-1 text-gray-700 break-all">POST {window.location.origin}/api/payments/webhook</code>
              <button onClick={() => copyText(`${window.location.origin}/api/payments/webhook`)} className="text-primary-600 hover:text-primary-800 flex-shrink-0 p-1"><Copy size={12} /></button>
            </div>
            <div className="text-xs text-primary-600 mt-2">Документация: Настройки → Документация API</div>
          </div>
        </div>
      )}

      {detailId && <PaymentDetailModal paymentId={detailId} onClose={() => setDetailId(null)} />}
    </div>
  )
}
