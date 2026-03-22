import { useEffect, useState, useCallback } from 'react'
import { partnersAPI } from '@/api'
import { fmt, fmtDate } from '@/utils'
import { Button, Modal, Input, Select, Avatar, Badge, Table, Tr, Td, Empty, Spinner, Textarea } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { PartnerModal } from '@/components/modals'
import { Plus, Edit2, Trash2, ChevronRight } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const COLORS = ['#534AB7','#1D9E75','#BA7517','#E24B4A','#378ADD','#D4537E']

const EMPTY_FORM = {
  name: '', role_label: 'Партнёр', tg_username: '', tg_id: '',
  share_percent: '', avatar_color: '#534AB7', initials: '', notes: '',
  initial_investment: '0', initial_returned: '0', initial_dividends: '0',
}

function PartnerForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial ? {
    ...initial,
    share_percent: initial.share_percent ?? '',
    initial_investment: initial.initial_investment ?? '0',
    initial_returned: initial.initial_returned ?? '0',
    initial_dividends: initial.initial_dividends ?? '0',
  } : { ...EMPTY_FORM })
  const [loading, setLoading] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload = {
        ...form,
        share_percent: form.share_percent !== '' ? parseFloat(form.share_percent) : null,
        initial_investment: parseFloat(form.initial_investment) || 0,
        initial_returned: parseFloat(form.initial_returned) || 0,
        initial_dividends: parseFloat(form.initial_dividends) || 0,
      }
      if (initial?.id) await partnersAPI.update(initial.id, payload)
      else await partnersAPI.create(payload)
      toast.success(initial?.id ? 'Обновлено' : 'Партнёр добавлен')
      onSave?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Имя" value={form.name} onChange={e => set('name', e.target.value)} required placeholder="Артём" />
        <Select label="Роль" value={form.role_label} onChange={e => set('role_label', e.target.value)}>
          <option>Партнёр</option>
          <option>Инвестор</option>
          <option>Соучредитель</option>
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Telegram username" value={form.tg_username} onChange={e => set('tg_username', e.target.value)} placeholder="@username" />
        <Input label="Telegram ID" value={form.tg_id} onChange={e => set('tg_id', e.target.value)} placeholder="123456789" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Доля %" type="number" step="0.1" value={form.share_percent} onChange={e => set('share_percent', e.target.value)} placeholder="33.3" />
        <Input label="Инициалы (для аватара)" value={form.initials} onChange={e => set('initials', e.target.value)} placeholder="АР" maxLength={3} />
      </div>
      <div>
        <label className="text-xs font-medium text-gray-500 mb-1.5 block">Цвет аватара</label>
        <div className="flex gap-2">
          {COLORS.map(c => (
            <button key={c} type="button" onClick={() => set('avatar_color', c)}
              className={`w-7 h-7 rounded-full transition-all ${form.avatar_color === c ? 'ring-2 ring-offset-2 ring-gray-400 scale-110' : ''}`}
              style={{ background: c }}
            />
          ))}
        </div>
      </div>
      <div className="border-t border-gray-100 pt-4">
        <div className="text-xs font-medium text-gray-500 mb-3">Начальные данные (до начала учёта)</div>
        <div className="grid grid-cols-3 gap-3">
          <Input label="Вложено всего ₽" type="number" value={form.initial_investment} onChange={e => set('initial_investment', e.target.value)} />
          <Input label="Возвращено ₽" type="number" value={form.initial_returned} onChange={e => set('initial_returned', e.target.value)} />
          <Input label="Выплачено ДВД ₽" type="number" value={form.initial_dividends} onChange={e => set('initial_dividends', e.target.value)} />
        </div>
      </div>
      <Textarea label="Заметки (только для администратора)" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} placeholder="Любые внутренние заметки..." />
      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>{initial?.id ? 'Сохранить' : 'Добавить'}</Button>
      </div>
    </form>
  )
}

export default function PartnersPage() {
  const [partners, setPartners] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const [detailId, setDetailId] = useState(null)
  const { isAdmin, isEditor } = useAuthStore()

  const load = useCallback(() => {
    setLoading(true)
    partnersAPI.list().then(r => setPartners(r.data)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    if (!confirm('Деактивировать партнёра?')) return
    await partnersAPI.delete(id)
    toast.success('Деактивирован')
    load()
  }

  return (
    <div>
      <PageHeader title="Партнёры и инвесторы" subtitle={`${partners.length} участников`}>
        {isAdmin() && (
          <Button variant="primary" size="sm" onClick={() => setModal('add')}>
            <Plus size={13} /> Добавить
          </Button>
        )}
      </PageHeader>

      <div className="p-3 md:p-5">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : partners.length === 0 ? (
          <Empty text="Партнёры не добавлены" action={
            isAdmin() && <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal('add')}><Plus size={13} />Добавить</Button>
          } />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {partners.map(p => (
              <div
                key={p.id}
                onClick={() => setDetailId(p.id)}
                className="bg-white border border-gray-100 rounded-xl p-5 cursor-pointer hover:border-primary-200 hover:shadow-sm transition-all group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <Avatar name={p.initials || p.name} color={p.avatar_color} size="lg" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-base">{p.name}</div>
                    <div className="text-xs text-gray-400">{p.role_label}{p.tg_username ? ` · @${p.tg_username}` : ''}</div>
                  </div>
                  <ChevronRight size={16} className="text-gray-300 group-hover:text-primary-400 transition-colors" />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-gray-50 rounded-lg p-2.5">
                    <div className="text-xs text-gray-400 mb-0.5">Вложено</div>
                    <div className="text-sm font-medium">{fmt(p.initial_investment)}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2.5">
                    <div className="text-xs text-gray-400 mb-0.5">ДВД выплачено</div>
                    <div className="text-sm font-medium text-success-600">{fmt(p.initial_dividends)}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-2.5">
                    <div className="text-xs text-gray-400 mb-0.5">Долг</div>
                    <div className={`text-sm font-medium ${(p.initial_investment - p.initial_returned) > 0 ? 'text-warn-600' : 'text-success-600'}`}>
                      {fmt(Math.max(0, p.initial_investment - p.initial_returned))}
                    </div>
                  </div>
                </div>
                {isAdmin() && (
                  <div className="flex gap-1 mt-3 pt-3 border-t border-gray-50 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                    <Button size="sm" variant="ghost" onClick={() => setModal(p)}><Edit2 size={12} /> Редактировать</Button>
                    <Button size="sm" variant="danger" onClick={() => handleDelete(p.id)}><Trash2 size={12} /> Удалить</Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal === 'add' ? 'Новый партнёр' : 'Редактировать партнёра'} size="lg">
        {modal && <PartnerForm initial={modal === 'add' ? null : modal} onSave={() => { setModal(null); load() }} onClose={() => setModal(null)} />}
      </Modal>

      {detailId && <PartnerModal partnerId={detailId} onClose={() => setDetailId(null)} />}
    </div>
  )
}
