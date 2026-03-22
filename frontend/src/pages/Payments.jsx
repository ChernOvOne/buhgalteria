import { useEffect, useState, useCallback } from 'react'
import { paymentsAPI } from '@/api'
import { fmt, fmtDate, fmtDateTime, today, monthStart } from '@/utils'
import { Button, Input, Modal, Table, Tr, Td, Badge, Empty, Spinner } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Trash2, Copy, Eye, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const PLAN_COLORS = {
  '1m': 'info', '3m': 'success', '6m': 'warn', '12m': 'income',
}

// ── Попап деталей платежа ─────────────────────────────────────────────────────
function PaymentDetailModal({ paymentId, onClose }) {
  const [p, setP] = useState(null)
  useEffect(() => {
    paymentsAPI.get(paymentId).then(r => setP(r.data))
  }, [paymentId])

  if (!p) return (
    <Modal open onClose={onClose} title="Платёж">
      <div className="flex justify-center py-8"><Spinner /></div>
    </Modal>
  )

  const isExpired = p.sub_end && new Date(p.sub_end) < new Date()
  const isExpiringSoon = p.sub_end && !isExpired && (new Date(p.sub_end) - new Date()) < 3 * 86400000

  return (
    <Modal open onClose={onClose} title={`Платёж — ${fmt(p.amount)}`} size="md">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400 mb-1">Сумма</div>
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
            ['ID клиента', p.customer_id || '—'],
            ['Источник', p.source || '—'],
            ['Внешний ID', p.external_id || '—'],
            ['Дата оплаты', fmtDate(p.date)],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-gray-50 pb-2">
              <span className="text-gray-400">{k}</span>
              <span className="font-medium text-right max-w-48 truncate">{v}</span>
            </div>
          ))}
        </div>

        {(p.sub_start || p.sub_end) && (
          <div className={`p-3 rounded-xl border ${
            isExpired ? 'bg-danger-50 border-danger-100' :
            isExpiringSoon ? 'bg-warn-50 border-warn-100' :
            'bg-success-50 border-success-100'
          }`}>
            <div className="flex items-center gap-2 text-sm">
              {isExpired ? <AlertCircle size={14} className="text-danger-600" /> :
               isExpiringSoon ? <Clock size={14} className="text-warn-600" /> :
               <CheckCircle size={14} className="text-success-600" />}
              <span className={isExpired ? 'text-danger-600' : isExpiringSoon ? 'text-warn-600' : 'text-success-600'}>
                {isExpired ? 'Подписка истекла' : isExpiringSoon ? 'Истекает скоро' : 'Подписка активна'}
              </span>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {p.sub_start && `Начало: ${fmtDate(p.sub_start)}`}
              {p.sub_start && p.sub_end && ' · '}
              {p.sub_end && `Конец: ${fmtDate(p.sub_end)}`}
            </div>
          </div>
        )}

        {p.raw_data && (
          <details className="text-xs">
            <summary className="text-gray-400 cursor-pointer hover:text-gray-600">Исходный JSON запрос</summary>
            <pre className="bg-gray-50 rounded-lg p-3 mt-2 overflow-auto max-h-48 text-xs font-mono">
              {JSON.stringify(p.raw_data, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </Modal>
  )
}

// ── Главная страница ──────────────────────────────────────────────────────────
export default function PaymentsPage() {
  const [payments, setPayments] = useState([])
  const [stats, setStats]       = useState(null)
  const [keys, setKeys]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [tab, setTab]           = useState('payments')
  const [detailId, setDetailId] = useState(null)
  const [newKeyName, setNewKeyName] = useState('')
  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo]     = useState(today())
  const [search, setSearch]     = useState('')
  const { isAdmin } = useAuthStore()

  const loadPayments = useCallback(async () => {
    setLoading(true)
    try {
      const [pRes, sRes] = await Promise.all([
        paymentsAPI.list({ date_from: dateFrom, date_to: dateTo, search: search || undefined }),
        paymentsAPI.stats({ date_from: dateFrom, date_to: dateTo }),
      ])
      setPayments(pRes.data)
      setStats(sRes.data)
    } finally { setLoading(false) }
  }, [dateFrom, dateTo, search])

  const loadKeys = useCallback(async () => {
    if (isAdmin()) {
      const r = await paymentsAPI.listKeys()
      setKeys(r.data)
    }
  }, [])

  useEffect(() => { loadPayments() }, [loadPayments])
  useEffect(() => { loadKeys() }, [loadKeys])

  const handleDeletePayment = async (id) => {
    if (!confirm('Удалить платёж и связанный доход?')) return
    await paymentsAPI.delete(id)
    toast.success('Удалено')
    loadPayments()
  }

  const handleCreateKey = async (e) => {
    e.preventDefault()
    if (!newKeyName) return
    await paymentsAPI.createKey({ name: newKeyName })
    toast.success('Ключ создан')
    setNewKeyName('')
    loadKeys()
  }

  const handleDeleteKey = async (id) => {
    if (!confirm('Отозвать ключ?')) return
    await paymentsAPI.deleteKey(id)
    toast.success('Ключ отозван')
    loadKeys()
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    toast.success('Скопировано')
  }

  const getBaseUrl = () => window.location.origin

  return (
    <div>
      <PageHeader title="Платежи" subtitle="Входящие оплаты через API">
      </PageHeader>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-100 bg-white px-4">
        {[['payments','Платежи'],['keys','API ключи'],['docs','Документация']].map(([k,v]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-3 text-sm transition-all ${tab===k ? 'text-primary-600 border-b-2 border-primary-600 font-medium' : 'text-gray-400 hover:text-gray-600'}`}>
            {v}
          </button>
        ))}
      </div>

      {/* Payments tab */}
      {tab === 'payments' && (
        <div>
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 p-3 md:p-4">
              <div className="bg-white border border-gray-100 rounded-xl p-3">
                <div className="text-xs text-gray-400 mb-1">Сумма за период</div>
                <div className="text-lg font-medium text-success-600">{fmt(stats.total_amount)}</div>
                <div className="text-xs text-gray-400">{stats.total_count} платежей</div>
              </div>
              <div className="bg-white border border-gray-100 rounded-xl p-3">
                <div className="text-xs text-gray-400 mb-1">Сегодня</div>
                <div className="text-lg font-medium">{fmt(stats.today_amount)}</div>
                <div className="text-xs text-gray-400">{stats.today_count} платежей</div>
              </div>
              <div className="bg-white border border-gray-100 rounded-xl p-3">
                <div className="text-xs text-gray-400 mb-1">Активных подписок</div>
                <div className="text-lg font-medium text-primary-600">{stats.active_subscriptions}</div>
              </div>
              <div className={`border rounded-xl p-3 ${stats.expiring_soon > 0 ? 'bg-warn-50 border-warn-100' : 'bg-white border-gray-100'}`}>
                <div className="text-xs text-gray-400 mb-1">Истекают через 3 дня</div>
                <div className={`text-lg font-medium ${stats.expiring_soon > 0 ? 'text-warn-600' : ''}`}>
                  {stats.expiring_soon}
                </div>
              </div>
            </div>
          )}

          {/* По тарифам */}
          {stats?.plans?.length > 0 && (
            <div className="px-3 md:px-4 pb-3">
              <div className="flex gap-2 flex-wrap">
                {stats.plans.map(p => (
                  <div key={p.tag || p.plan} className="bg-white border border-gray-100 rounded-xl px-3 py-2 text-sm">
                    <span className="font-medium">{p.plan || p.tag || 'Без тарифа'}</span>
                    <span className="text-gray-400 ml-2">{p.count} шт · {fmt(p.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex gap-2 px-3 md:px-4 pb-3 flex-wrap">
            <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-36" />
            <Input type="date" value={dateTo}   onChange={e => setDateTo(e.target.value)}   className="w-36" />
            <Input placeholder="Поиск по email, ID..." value={search} onChange={e => setSearch(e.target.value)} className="w-52" />
          </div>

          {/* Table */}
          <div className="mx-3 md:mx-4 bg-white border border-gray-100 rounded-xl overflow-hidden">
            {loading ? (
              <div className="flex justify-center py-12"><Spinner /></div>
            ) : payments.length === 0 ? (
              <Empty text="Платежей нет — настройте webhook и отправьте первый запрос" />
            ) : (
              <Table headers={['Дата','Клиент','Тариф','Подписка','Сумма','']}>
                {payments.map(p => {
                  const isExpired = p.sub_end && new Date(p.sub_end) < new Date()
                  const isExpiringSoon = p.sub_end && !isExpired && (new Date(p.sub_end) - new Date()) < 3 * 86400000
                  return (
                    <Tr key={p.id} className="group">
                      <Td className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(p.date)}</Td>
                      <Td>
                        <div className="text-sm font-medium">{p.customer_name || p.customer_id || '—'}</div>
                        {p.customer_email && <div className="text-xs text-gray-400">{p.customer_email}</div>}
                      </Td>
                      <Td>
                        {p.plan && <Badge variant={PLAN_COLORS[p.plan_tag] || 'info'}>{p.plan}</Badge>}
                      </Td>
                      <Td>
                        {p.sub_end ? (
                          <span className={`text-xs font-medium ${isExpired ? 'text-danger-600' : isExpiringSoon ? 'text-warn-600' : 'text-success-600'}`}>
                            {isExpired ? '✗ истекла' : isExpiringSoon ? `⚠ ${fmtDate(p.sub_end)}` : `✓ до ${fmtDate(p.sub_end)}`}
                          </span>
                        ) : '—'}
                      </Td>
                      <Td className="font-medium text-success-600">{fmt(p.amount)}</Td>
                      <Td>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => setDetailId(p.id)}
                            className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700">
                            <Eye size={12} />
                          </button>
                          {isAdmin() && (
                            <button onClick={() => handleDeletePayment(p.id)}
                              className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600">
                              <Trash2 size={12} />
                            </button>
                          )}
                        </div>
                      </Td>
                    </Tr>
                  )
                })}
              </Table>
            )}
          </div>
        </div>
      )}

      {/* API Keys tab */}
      {tab === 'keys' && isAdmin() && (
        <div className="p-3 md:p-4 space-y-4">
          <form onSubmit={handleCreateKey} className="flex gap-3">
            <Input
              placeholder="Название ключа (например: Бот VPN)"
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" variant="primary"><Plus size={13} /> Создать ключ</Button>
          </form>
          <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
            <Table headers={['Название','Ключ','Запросов','Последнее использование','']}>
              {keys.map(k => (
                <Tr key={k.id} className="group">
                  <Td className="font-medium">{k.name}</Td>
                  <Td>
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono bg-gray-50 px-2 py-0.5 rounded max-w-48 truncate select-all">
                        {k.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(k.key)}
                        className="p-1.5 rounded hover:bg-primary-50 hover:text-primary-600 text-gray-400 flex-shrink-0"
                        title="Скопировать ключ"
                      >
                        <Copy size={12} />
                      </button>
                    </div>
                  </Td>
                  <Td className="text-gray-500">{k.request_count || 0}</Td>
                  <Td className="text-xs text-gray-400">
                    {k.last_used ? fmtDateTime(k.last_used) : 'Не использовался'}
                  </Td>
                  <Td>
                    <button onClick={() => handleDeleteKey(k.id)}
                      className="p-1.5 rounded opacity-0 group-hover:opacity-100 hover:bg-danger-50 text-gray-400 hover:text-danger-600">
                      <Trash2 size={12} />
                    </button>
                  </Td>
                </Tr>
              ))}
            </Table>
          </div>
        </div>
      )}

      {/* Docs tab */}
      {tab === 'docs' && (
        <div className="p-3 md:p-4 space-y-4 max-w-3xl">
          <div className="bg-white border border-gray-100 rounded-xl p-5">
            <div className="font-medium mb-2 text-sm">Endpoint для приёма платежей</div>
            <div className="flex items-center gap-2 bg-gray-50 rounded-lg p-3 mb-4">
              <code className="text-sm font-mono flex-1">POST {getBaseUrl()}/api/payments/webhook</code>
              <button onClick={() => copyToClipboard(`${getBaseUrl()}/api/payments/webhook`)}
                className="text-gray-400 hover:text-primary-600 p-1">
                <Copy size={14} />
              </button>
            </div>

            <div className="font-medium mb-2 text-sm">Структура JSON</div>
            <pre className="bg-gray-50 rounded-lg p-4 text-xs font-mono overflow-auto">
{`{
  "api_key": "ВАШ_КЛЮЧ",          // обязательно
  "amount": 299.00,                 // обязательно, сумма в рублях
  "external_id": "PAY-12345",      // уникальный ID для защиты от дублей
  "customer_email": "user@mail.com",
  "customer_id": "tg_123456",      // Telegram ID или любой другой
  "customer_name": "Иван Иванов",
  "plan": "3 месяц VPN",           // отображаемое название тарифа
  "plan_tag": "3m",                 // машинный тег: 1m, 3m, 6m, 12m
  "subscription_start": "2026-03-22",
  "subscription_end": "2026-06-22",
  "description": "Оплата VPN",
  "source": "bot_1"                 // имя источника
}`}
            </pre>

            <div className="font-medium mb-2 mt-4 text-sm">Пример curl</div>
            <pre className="bg-gray-50 rounded-lg p-4 text-xs font-mono overflow-auto">
{`curl -X POST ${getBaseUrl()}/api/payments/webhook \\
  -H "Content-Type: application/json" \\
  -d '{
    "api_key": "ВАШ_КЛЮЧ",
    "amount": 299,
    "customer_id": "123456",
    "plan": "1 месяц VPN",
    "plan_tag": "1m",
    "subscription_end": "2026-04-22"
  }'`}
            </pre>

            <div className="font-medium mb-2 mt-4 text-sm">Ответы сервера</div>
            <div className="space-y-2 text-sm">
              <div className="flex gap-2 items-start">
                <Badge variant="success">200</Badge>
                <code className="text-xs font-mono">{`{"ok": true, "status": "created", "payment_id": "..."}`}</code>
              </div>
              <div className="flex gap-2 items-start">
                <Badge variant="warn">200</Badge>
                <code className="text-xs font-mono">{`{"ok": true, "status": "duplicate"}`} — платёж с таким external_id уже есть</code>
              </div>
              <div className="flex gap-2 items-start">
                <Badge variant="danger">401</Badge>
                <code className="text-xs font-mono">Неверный API ключ</code>
              </div>
            </div>
          </div>

          <div className="bg-primary-50 border border-primary-100 rounded-xl p-4 text-sm text-primary-600">
            <div className="font-medium mb-1">Как это работает</div>
            <div className="text-xs space-y-1 text-primary-600">
              <div>• Каждый принятый платёж автоматически создаёт запись дохода</div>
              <div>• Срок подписки отслеживается — на дашборде видны истекающие через 3 дня</div>
              <div>• Все платежи видны в разделе Платежи с деталями клиента</div>
              <div>• Создайте отдельный API-ключ для каждого бота/источника</div>
            </div>
          </div>
        </div>
      )}

      {detailId && (
        <PaymentDetailModal paymentId={detailId} onClose={() => setDetailId(null)} />
      )}
    </div>
  )
}
