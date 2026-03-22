import { useEffect, useState } from 'react'
import { partnersAPI, reportsAPI } from '@/api'
import { fmt, fmtDate, fmtDateShort, INKAS_LABELS, downloadBlob, today, yearStart } from '@/utils'
import { Modal, Button, Avatar, Badge, Spinner, Textarea, Input, Select } from '@/components/ui'
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { FileDown, Send, Plus, Trash2 } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const INKAS_COLORS = { dividend: 'success', return_inv: 'info', investment: 'warn' }

export function PartnerModal({ partnerId, onClose }) {
  const [partner, setPartner] = useState(null)
  const [tab, setTab] = useState('ops')
  const [showInkasForm, setShowInkasForm] = useState(false)
  const [inkasForm, setInkasForm] = useState({ type: 'dividend', amount: '', date: today(), month_label: '', description: '' })
  const [saving, setSaving] = useState(false)
  const { isEditor } = useAuthStore()

  const load = () => {
    partnersAPI.get(partnerId).then((r) => setPartner(r.data)).catch(() => toast.error('Ошибка загрузки'))
  }

  useEffect(() => { load() }, [partnerId])

  const handleAddInkas = async (e) => {
    e.preventDefault()
    if (!inkasForm.amount) return
    setSaving(true)
    try {
      await partnersAPI.createInkas({ ...inkasForm, partner_id: partnerId, amount: parseFloat(inkasForm.amount) })
      toast.success('Выплата добавлена')
      setShowInkasForm(false)
      setInkasForm({ type: 'dividend', amount: '', date: today(), month_label: '', description: '' })
      load()
    } catch { toast.error('Ошибка сохранения') }
    finally { setSaving(false) }
  }

  const handleDeleteInkas = async (id) => {
    if (!confirm('Удалить запись?')) return
    await partnersAPI.deleteInkas(id)
    toast.success('Удалено')
    load()
  }

  const handleExport = async () => {
    try {
      const res = await reportsAPI.pdf({ date_from: yearStart(), date_to: today() })
      downloadBlob(res.data, `partner_${partner.name}.pdf`)
    } catch { toast.error('Ошибка экспорта') }
  }

  if (!partner) return (
    <Modal open onClose={onClose} title="Загрузка...">
      <div className="flex justify-center py-8"><Spinner /></div>
    </Modal>
  )

  const { stats } = partner

  // Данные для графика дивидендов
  const dvdData = stats.records
    .filter((r) => r.type === 'dividend')
    .slice(0, 8)
    .reverse()
    .map((r) => ({ month: r.month_label || fmtDateShort(r.date), amount: r.amount }))

  return (
    <Modal
      open
      onClose={onClose}
      title=""
      size="lg"
      footer={
        <>
          {isEditor() && (
            <Button variant="primary" size="sm" onClick={() => setShowInkasForm(true)}>
              <Plus size={13} /> Начислить выплату
            </Button>
          )}
          <Button size="sm" onClick={handleExport}>
            <FileDown size={13} /> Экспорт PDF
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>Закрыть</Button>
        </>
      }
    >
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Avatar name={partner.name} color={partner.avatar_color} size="lg" />
        <div>
          <div className="text-lg font-medium">{partner.name}</div>
          <div className="text-sm text-gray-400">{partner.role_label}{partner.tg_username ? ` · @${partner.tg_username}` : ''}</div>
        </div>
        <Badge variant={partner.is_active ? 'success' : 'gray'} className="ml-auto">
          {partner.is_active ? 'Активен' : 'Неактивен'}
        </Badge>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="text-xs text-gray-400 mb-1">Вложено</div>
          <div className="text-base font-medium">{fmt(stats.total_invested)}</div>
        </div>
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="text-xs text-gray-400 mb-1">ДВД всего</div>
          <div className="text-base font-medium text-success-600">{fmt(stats.total_dividends)}</div>
        </div>
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="text-xs text-gray-400 mb-1">Остаток долга</div>
          <div className={`text-base font-medium ${stats.remaining_debt > 0 ? 'text-warn-600' : 'text-success-600'}`}>
            {stats.remaining_debt > 0 ? fmt(stats.remaining_debt) : 'Погашен'}
          </div>
        </div>
        <div className="bg-gray-50 rounded-xl p-3">
          <div className="text-xs text-gray-400 mb-1">Прогноз (след.)</div>
          <div className="text-base font-medium text-primary-600">
            {stats.forecast_next ? `~${fmt(stats.forecast_next)}` : '—'}
          </div>
        </div>
      </div>

      {/* Progress */}
      {stats.total_invested > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-gray-500">Возврат инвестиций</span>
            <span className="font-medium">{Math.round(Math.min(100, stats.total_returned / stats.total_invested * 100))}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-warn-600 transition-all duration-500"
              style={{ width: `${Math.min(100, stats.total_returned / stats.total_invested * 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>Возвращено: {fmt(stats.total_returned)}</span>
            <span>Вложено: {fmt(stats.total_invested)}</span>
          </div>
        </div>
      )}

      {/* Dividend chart */}
      {dvdData.length > 0 && (
        <div className="mb-5">
          <div className="text-xs font-medium text-gray-500 mb-2">Динамика дивидендов</div>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={dvdData} margin={{ left: -20 }}>
              <XAxis dataKey="month" tick={{ fontSize: 9, fill: '#aaa' }} tickLine={false} axisLine={false} />
              <Tooltip formatter={(v) => fmt(v)} />
              <Bar dataKey="amount" fill="#BA7517" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-100 mb-4">
        {[['ops','Операции'],['stats','Статистика'],['notes','Заметки']].map(([k, v]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm transition-all ${
              tab === k
                ? 'text-primary-600 border-b-2 border-primary-600 font-medium'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {tab === 'ops' && (
        <div className="space-y-1">
          {stats.records.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-6">Операций нет</div>
          ) : stats.records.slice(0, 20).map((r) => (
            <div key={r.id} className="flex items-center gap-3 py-2.5 border-b border-gray-50 last:border-0 group">
              <div className="text-xs text-gray-400 w-20 flex-shrink-0">{fmtDate(r.date)}</div>
              <Badge variant={INKAS_COLORS[r.type]}>{INKAS_LABELS[r.type]}</Badge>
              <div className="flex-1 text-xs text-gray-500">{r.description || r.month_label || ''}</div>
              <div className="font-medium text-sm">{fmt(r.amount)}</div>
              {isEditor() && (
                <button
                  onClick={() => handleDeleteInkas(r.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-300 hover:text-danger-600 transition-all"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'stats' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Среднее ДВД/мес</div>
            <div className="text-base font-medium">{fmt(stats.avg_dividend)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Последняя выплата</div>
            <div className="text-base font-medium">{stats.last_dividend_amount ? fmt(stats.last_dividend_amount) : '—'}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Дата последней выплаты</div>
            <div className="text-base font-medium">{fmtDate(stats.last_dividend_date)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Всего выплат</div>
            <div className="text-base font-medium">
              {stats.records.filter((r) => r.type === 'dividend').length}
            </div>
          </div>
        </div>
      )}

      {tab === 'notes' && (
        <div>
          <Textarea
            placeholder="Заметки об участнике (видны только администратору)..."
            value={partner.notes || ''}
            rows={4}
            readOnly
          />
        </div>
      )}

      {/* Inkas Form */}
      {showInkasForm && (
        <div className="mt-4 p-4 bg-gray-50 rounded-xl border border-gray-100">
          <div className="text-sm font-medium mb-3">Новая выплата</div>
          <form onSubmit={handleAddInkas} className="grid grid-cols-2 gap-3">
            <Select
              label="Тип"
              value={inkasForm.type}
              onChange={(e) => setInkasForm({ ...inkasForm, type: e.target.value })}
            >
              <option value="dividend">ДВД (дивиденды)</option>
              <option value="return_inv">Возврат инвестиций</option>
              <option value="investment">Новое вложение</option>
            </Select>
            <Input
              label="Сумма ₽"
              type="number"
              placeholder="50000"
              value={inkasForm.amount}
              onChange={(e) => setInkasForm({ ...inkasForm, amount: e.target.value })}
              required
            />
            <Input
              label="Дата"
              type="date"
              value={inkasForm.date}
              onChange={(e) => setInkasForm({ ...inkasForm, date: e.target.value })}
            />
            <Input
              label="Период (напр. МАРТ 2026)"
              placeholder="МАРТ 2026"
              value={inkasForm.month_label}
              onChange={(e) => setInkasForm({ ...inkasForm, month_label: e.target.value })}
            />
            <div className="col-span-2 flex gap-2 justify-end">
              <Button size="sm" variant="ghost" type="button" onClick={() => setShowInkasForm(false)}>Отмена</Button>
              <Button size="sm" variant="primary" type="submit" loading={saving}>Сохранить</Button>
            </div>
          </form>
        </div>
      )}
    </Modal>
  )
}

export default PartnerModal
