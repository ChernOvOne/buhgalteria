import { useEffect, useState, useCallback } from 'react'
import { adsAPI } from '@/api'
import { fmt, fmtDate, today, monthStart } from '@/utils'
import { Button, Input, Modal, Table, Tr, Td, Badge, Empty, Spinner, Textarea } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Edit2, Trash2, ExternalLink, TrendingUp } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  date: today(), channel_name: '', channel_url: '',
  format: '', amount: '', subscribers_gained: '', screenshot_url: '', notes: '',
}

function AdForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial ? {
    ...initial,
    amount: initial.amount ?? '',
    subscribers_gained: initial.subscribers_gained ?? '',
  } : { ...EMPTY_FORM })
  const [loading, setLoading] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        subscribers_gained: form.subscribers_gained !== '' ? parseInt(form.subscribers_gained) : null,
      }
      if (initial?.id) await adsAPI.update(initial.id, payload)
      else await adsAPI.create(payload)
      toast.success(initial?.id ? 'Обновлено' : 'Кампания добавлена')
      onSave?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Дата" type="date" value={form.date} onChange={e => set('date', e.target.value)} required />
        <Input label="Формат" value={form.format} onChange={e => set('format', e.target.value)} placeholder="2/48, 1/24, 24/24" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Название канала" value={form.channel_name} onChange={e => set('channel_name', e.target.value)} placeholder="TikTok Updates 🔥" required />
        <Input label="Ссылка на канал" value={form.channel_url} onChange={e => set('channel_url', e.target.value)} placeholder="https://t.me/..." />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Сумма ₽" type="number" step="0.01" value={form.amount} onChange={e => set('amount', e.target.value)} required placeholder="10000" />
        <Input label="Привлечено ПДП" type="number" value={form.subscribers_gained} onChange={e => set('subscribers_gained', e.target.value)} placeholder="1234" />
      </div>
      <Input label="Скриншот (ссылка)" value={form.screenshot_url} onChange={e => set('screenshot_url', e.target.value)} placeholder="https://disk.yandex.ru/..." />
      <Textarea label="Заметки" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} />
      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>{initial?.id ? 'Сохранить' : 'Добавить'}</Button>
      </div>
    </form>
  )
}

export default function AdsPage() {
  const [campaigns, setCampaigns] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const [filters, setFilters] = useState({ date_from: monthStart(), date_to: today() })
  const { isEditor } = useAuthStore()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [camRes, sumRes] = await Promise.all([
        adsAPI.list(filters),
        adsAPI.summary(filters),
      ])
      setCampaigns(camRes.data)
      setSummary(sumRes.data)
    } finally { setLoading(false) }
  }, [filters])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    if (!confirm('Удалить кампанию?')) return
    await adsAPI.delete(id)
    toast.success('Удалено')
    load()
  }

  return (
    <div>
      <PageHeader title="Реклама" subtitle="Трекинг кампаний и ROI">
        {isEditor() && (
          <Button variant="primary" size="sm" onClick={() => setModal('add')}>
            <Plus size={13} /> Добавить кампанию
          </Button>
        )}
      </PageHeader>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 p-3 md:p-5 pb-0">
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs text-gray-400 mb-1">Потрачено</div>
            <div className="text-xl font-medium">{fmt(summary.total_spent)}</div>
          </div>
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs text-gray-400 mb-1">Привлечено ПДП</div>
            <div className="text-xl font-medium">{summary.total_subscribers?.toLocaleString('ru') || '—'}</div>
          </div>
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs text-gray-400 mb-1">Стоимость 1 ПДП</div>
            <div className="text-xl font-medium text-success-600">{summary.cost_per_sub ? fmt(summary.cost_per_sub) : '—'}</div>
          </div>
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs text-gray-400 mb-1">Кампаний</div>
            <div className="text-xl font-medium">{summary.campaigns_count}</div>
            {summary.best_channel && (
              <div className="text-xs text-gray-400 mt-1 truncate" title={summary.best_channel.name}>
                Лучший: {summary.best_channel.name}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 p-3 md:p-5 pb-0 flex-wrap">
        <Input type="date" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))} className="w-36" />
        <Input type="date" value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))} className="w-36" />
      </div>

      <div className="p-3 md:p-5">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : campaigns.length === 0 ? (
          <Empty text="Кампаний не найдено" action={
            isEditor() && <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal('add')}><Plus size={13} />Добавить</Button>
          } />
        ) : (
          <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
            <Table headers={['Дата', 'Формат', 'Канал', 'Сумма', 'ПДП', '₽/ПДП', 'Скрин', '']}>
              {campaigns.map(c => (
                <Tr key={c.id} className="group">
                  <Td className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(c.date)}</Td>
                  <Td><Badge variant="info">{c.format || '—'}</Badge></Td>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      {c.channel_url ? (
                        <a href={c.channel_url} target="_blank" rel="noreferrer"
                          className="text-sm font-medium text-primary-600 hover:underline flex items-center gap-1"
                          onClick={e => e.stopPropagation()}>
                          {c.channel_name} <ExternalLink size={10} />
                        </a>
                      ) : (
                        <span className="text-sm">{c.channel_name || '—'}</span>
                      )}
                    </div>
                  </Td>
                  <Td className="font-medium">{fmt(c.amount)}</Td>
                  <Td className="font-medium">{c.subscribers_gained?.toLocaleString('ru') || '—'}</Td>
                  <Td>
                    {c.cost_per_sub ? (
                      <span className={`font-medium text-sm ${c.cost_per_sub < 20 ? 'text-success-600' : c.cost_per_sub < 50 ? 'text-warn-600' : 'text-danger-600'}`}>
                        {fmt(c.cost_per_sub)}
                      </span>
                    ) : '—'}
                  </Td>
                  <Td>
                    {c.screenshot_url && (
                      <a href={c.screenshot_url} target="_blank" rel="noreferrer"
                        className="text-primary-600 hover:underline text-xs flex items-center gap-1">
                        <ExternalLink size={11} /> Скрин
                      </a>
                    )}
                  </Td>
                  <Td>
                    {isEditor() && (
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => setModal(c)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"><Edit2 size={12} /></button>
                        <button onClick={() => handleDelete(c.id)} className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600"><Trash2 size={12} /></button>
                      </div>
                    )}
                  </Td>
                </Tr>
              ))}
            </Table>
          </div>
        )}
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal === 'add' ? 'Новая кампания' : 'Редактировать кампанию'} size="lg">
        {modal && <AdForm initial={modal === 'add' ? null : modal} onSave={() => { setModal(null); load() }} onClose={() => setModal(null)} />}
      </Modal>
    </div>
  )
}
