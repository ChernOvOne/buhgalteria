import { useEffect, useState, useCallback } from 'react'
import { partnersAPI } from '@/api'
import { fmt, fmtDate, INKAS_LABELS, today } from '@/utils'
import { Button, Input, Select, Modal, Table, Tr, Td, Badge, Empty, Spinner, Avatar } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Trash2 } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const TYPE_COLORS = { dividend: 'success', return_inv: 'info', investment: 'warn' }

const EMPTY_FORM = { partner_id: '', type: 'dividend', amount: '', date: today(), month_label: '', description: '' }

export default function InkasPage() {
  const [records, setRecords] = useState([])
  const [partners, setPartners] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const { isEditor } = useAuthStore()
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const load = useCallback(async () => {
    setLoading(true)
    const [rRes, pRes] = await Promise.all([
      partnersAPI.listInkas(),
      partnersAPI.list(),
    ])
    setRecords(rRes.data)
    setPartners(pRes.data)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const getPartner = (id) => partners.find(p => p.id === id)

  const handleSave = async (e) => {
    e.preventDefault()
    if (!form.partner_id || !form.amount) return
    setSaving(true)
    try {
      await partnersAPI.createInkas({ ...form, amount: parseFloat(form.amount) })
      toast.success('Запись добавлена')
      setModal(false)
      setForm({ ...EMPTY_FORM })
      load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Ошибка') }
    finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Удалить запись?')) return
    await partnersAPI.deleteInkas(id)
    toast.success('Удалено')
    load()
  }

  const totalDvd = records.filter(r => r.type === 'dividend').reduce((s, r) => s + r.amount, 0)
  const totalRet = records.filter(r => r.type === 'return_inv').reduce((s, r) => s + r.amount, 0)
  const totalInv = records.filter(r => r.type === 'investment').reduce((s, r) => s + r.amount, 0)

  return (
    <div>
      <PageHeader title="Инкас" subtitle="Выплаты партнёрам и движение инвестиций">
        {isEditor() && (
          <Button variant="primary" size="sm" onClick={() => setModal(true)}>
            <Plus size={13} /> Добавить запись
          </Button>
        )}
      </PageHeader>

      <div className="grid grid-cols-3 gap-3 p-5 pb-0">
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs text-gray-400 mb-1">Дивиденды (всего)</div>
          <div className="text-xl font-medium text-success-600">{fmt(totalDvd)}</div>
        </div>
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs text-gray-400 mb-1">Возврат инвестиций</div>
          <div className="text-xl font-medium text-primary-600">{fmt(totalRet)}</div>
        </div>
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs text-gray-400 mb-1">Новые вложения</div>
          <div className="text-xl font-medium text-warn-600">{fmt(totalInv)}</div>
        </div>
      </div>

      <div className="p-5">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : records.length === 0 ? (
          <Empty text="Записей нет" action={
            isEditor() && <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal(true)}><Plus size={13} />Добавить</Button>
          } />
        ) : (
          <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
            <Table headers={['Дата', 'Период', 'Партнёр', 'Тип', 'Описание', 'Сумма', '']}>
              {records.map(r => {
                const p = getPartner(r.partner_id)
                return (
                  <Tr key={r.id} className="group">
                    <Td className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(r.date)}</Td>
                    <Td className="text-xs text-gray-500">{r.month_label || '—'}</Td>
                    <Td>
                      {p && (
                        <div className="flex items-center gap-2">
                          <Avatar name={p.initials || p.name} color={p.avatar_color} size="sm" />
                          <span className="text-sm font-medium">{p.name}</span>
                        </div>
                      )}
                    </Td>
                    <Td><Badge variant={TYPE_COLORS[r.type]}>{INKAS_LABELS[r.type]}</Badge></Td>
                    <Td className="text-xs text-gray-500">{r.description || '—'}</Td>
                    <Td className="font-medium">{fmt(r.amount)}</Td>
                    <Td>
                      {isEditor() && (
                        <button onClick={() => handleDelete(r.id)}
                          className="p-1.5 rounded opacity-0 group-hover:opacity-100 hover:bg-danger-50 text-gray-400 hover:text-danger-600 transition-all">
                          <Trash2 size={12} />
                        </button>
                      )}
                    </Td>
                  </Tr>
                )
              })}
            </Table>
          </div>
        )}
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title="Новая запись инкас"
        footer={<><Button variant="ghost" onClick={() => setModal(false)}>Отмена</Button><Button variant="primary" onClick={handleSave} loading={saving}>Сохранить</Button></>}>
        <div className="space-y-4">
          <Select label="Партнёр" value={form.partner_id} onChange={e => set('partner_id', e.target.value)}>
            <option value="">— Выберите партнёра —</option>
            {partners.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
          <Select label="Тип" value={form.type} onChange={e => set('type', e.target.value)}>
            <option value="dividend">ДВД (дивиденды)</option>
            <option value="return_inv">Возврат инвестиций</option>
            <option value="investment">Новое вложение</option>
          </Select>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Сумма ₽" type="number" value={form.amount} onChange={e => set('amount', e.target.value)} required placeholder="80000" />
            <Input label="Дата" type="date" value={form.date} onChange={e => set('date', e.target.value)} />
          </div>
          <Input label="Период (напр. МАРТ 2026)" value={form.month_label} onChange={e => set('month_label', e.target.value)} placeholder="МАРТ 2026" />
          <Input label="Описание" value={form.description} onChange={e => set('description', e.target.value)} placeholder="Дивиденды за март" />
        </div>
      </Modal>
    </div>
  )
}
