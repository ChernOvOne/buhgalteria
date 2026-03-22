import { useEffect, useState, useCallback } from 'react'
import { serversAPI } from '@/api'
import { fmt, fmtDate, today } from '@/utils'
import { Button, Input, Modal, Table, Tr, Td, Badge, Empty, Spinner, Textarea } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Edit2, Trash2, ExternalLink, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  name: '', provider: '', ip_address: '', purpose: '',
  panel_url: '', monthly_cost: '', currency: 'RUB',
  payment_day: '', next_payment_date: '', notify_days_before: '5', notes: '',
}

function StatusIcon({ status, days }) {
  if (status === 'expired' || days < 0) return <AlertCircle size={14} className="text-danger-600" />
  if (status === 'warning' || days <= 5) return <Clock size={14} className="text-warn-600" />
  return <CheckCircle size={14} className="text-success-600" />
}

function StatusBadge({ status, days }) {
  if (days == null) return <Badge variant="gray">—</Badge>
  if (days < 0) return <Badge variant="danger">Просрочен</Badge>
  if (days === 0) return <Badge variant="danger">Сегодня</Badge>
  if (days <= 5) return <Badge variant="warn">через {days}д</Badge>
  return <Badge variant="success">через {days}д</Badge>
}

function ServerForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial ? {
    ...initial,
    monthly_cost: initial.monthly_cost ?? '',
    payment_day: initial.payment_day ?? '',
    next_payment_date: initial.next_payment_date ?? '',
    notify_days_before: initial.notify_days_before ?? 5,
  } : { ...EMPTY_FORM })
  const [loading, setLoading] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload = {
        ...form,
        monthly_cost: form.monthly_cost !== '' ? parseFloat(form.monthly_cost) : null,
        payment_day: form.payment_day !== '' ? parseInt(form.payment_day) : null,
        next_payment_date: form.next_payment_date || null,
        notify_days_before: parseInt(form.notify_days_before) || 5,
      }
      if (initial?.id) await serversAPI.update(initial.id, payload)
      else await serversAPI.create(payload)
      toast.success(initial?.id ? 'Обновлено' : 'Сервер добавлен')
      onSave?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Название" value={form.name} onChange={e => set('name', e.target.value)} required placeholder="ProCloud" />
        <Input label="Провайдер" value={form.provider} onChange={e => set('provider', e.target.value)} placeholder="ProCloud" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="IP адрес" value={form.ip_address} onChange={e => set('ip_address', e.target.value)} placeholder="185.22.x.x" className="font-mono" />
        <Input label="Назначение" value={form.purpose} onChange={e => set('purpose', e.target.value)} placeholder="Обход РФ + Польша" />
      </div>
      <Input label="Ссылка на панель управления" value={form.panel_url} onChange={e => set('panel_url', e.target.value)} placeholder="https://panel.provider.com" />
      <div className="grid grid-cols-3 gap-3">
        <Input label="Стоимость/мес ₽" type="number" value={form.monthly_cost} onChange={e => set('monthly_cost', e.target.value)} placeholder="5200" />
        <Input label="День оплаты (1-31)" type="number" min="1" max="31" value={form.payment_day} onChange={e => set('payment_day', e.target.value)} placeholder="16" />
        <Input label="Дата след. оплаты" type="date" value={form.next_payment_date} onChange={e => set('next_payment_date', e.target.value)} />
      </div>
      <Input label="Уведомлять за (дней)" type="number" value={form.notify_days_before} onChange={e => set('notify_days_before', e.target.value)} placeholder="5" />
      <Textarea label="Заметки" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} placeholder="Германия, обход для канала..." />
      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>{initial?.id ? 'Сохранить' : 'Добавить'}</Button>
      </div>
    </form>
  )
}

export default function ServersPage() {
  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const { isEditor } = useAuthStore()

  const load = useCallback(() => {
    setLoading(true)
    serversAPI.list().then(r => setServers(r.data)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    if (!confirm('Удалить сервер?')) return
    await serversAPI.delete(id)
    toast.success('Удалён')
    load()
  }

  const totalMonthly = servers.reduce((s, sv) => s + (sv.monthly_cost || 0), 0)
  const soonCount = servers.filter(s => s.days_until_payment != null && s.days_until_payment <= 7).length

  return (
    <div>
      <PageHeader title="Серверы" subtitle={`${servers.length} серверов · ${fmt(totalMonthly)}/мес`}>
        {isEditor() && (
          <Button variant="primary" size="sm" onClick={() => setModal('add')}>
            <Plus size={13} /> Добавить сервер
          </Button>
        )}
      </PageHeader>

      {soonCount > 0 && (
        <div className="mx-5 mt-4 p-3 bg-warn-50 border border-warn-100 rounded-xl flex items-center gap-2 text-sm text-warn-600">
          <AlertCircle size={14} />
          <span>{soonCount} {soonCount === 1 ? 'сервер требует' : 'сервера требуют'} оплаты в ближайшие 7 дней</span>
        </div>
      )}

      <div className="p-5">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : servers.length === 0 ? (
          <Empty text="Серверы не добавлены" action={
            isEditor() && <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal('add')}><Plus size={13} />Добавить</Button>
          } />
        ) : (
          <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
            <Table headers={['Статус', 'Название', 'IP', 'Назначение', 'Стоимость', 'Оплата', 'Панель', '']}>
              {servers.map(s => (
                <Tr key={s.id} className="group">
                  <Td><StatusIcon status={s.status} days={s.days_until_payment} /></Td>
                  <Td>
                    <div className="font-medium text-sm">{s.name}</div>
                    {s.provider && s.provider !== s.name && <div className="text-xs text-gray-400">{s.provider}</div>}
                  </Td>
                  <Td>
                    <span className="font-mono text-xs text-gray-500">{s.ip_address || '—'}</span>
                  </Td>
                  <Td className="text-xs text-gray-500 max-w-xs truncate">{s.purpose || '—'}</Td>
                  <Td className="font-medium">{s.monthly_cost ? fmt(s.monthly_cost) : '—'}</Td>
                  <Td>
                    <div className="flex flex-col gap-0.5">
                      <StatusBadge status={s.status} days={s.days_until_payment} />
                      {s.next_payment_date && (
                        <span className="text-xs text-gray-400">{fmtDate(s.next_payment_date)}</span>
                      )}
                    </div>
                  </Td>
                  <Td>
                    {s.panel_url && (
                      <a href={s.panel_url} target="_blank" rel="noreferrer"
                        className="text-primary-600 hover:underline inline-flex items-center gap-1 text-xs">
                        <ExternalLink size={11} /> Открыть
                      </a>
                    )}
                  </Td>
                  <Td>
                    {isEditor() && (
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => setModal(s)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
                          <Edit2 size={12} />
                        </button>
                        <button onClick={() => handleDelete(s.id)} className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600 transition-colors">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    )}
                  </Td>
                </Tr>
              ))}
            </Table>
          </div>
        )}
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal === 'add' ? 'Новый сервер' : 'Редактировать сервер'} size="lg">
        {modal && <ServerForm initial={modal === 'add' ? null : modal} onSave={() => { setModal(null); load() }} onClose={() => setModal(null)} />}
      </Modal>
    </div>
  )
}
