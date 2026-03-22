import { useEffect, useState, useCallback } from 'react'
import { transactionsAPI, categoriesAPI } from '@/api'
import { fmt, fmtDate, fmtDateTime, today, monthStart, toISO } from '@/utils'
import {
  Button, Input, Select, Modal, Table, Tr, Td,
  Badge, Empty, Spinner, SectionHeader,
} from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Search, FileDown, Trash2, Edit2, Paperclip, X } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  type: 'income',
  amount: '',
  date: today(),
  category_id: '',
  description: '',
  receipt_url: '',
}

function TransactionForm({ initial, categories, onSave, onClose, typeFixed }) {
  const [form, setForm] = useState(initial || { ...EMPTY_FORM, type: typeFixed || 'income' })
  const [loading, setLoading] = useState(false)
  const [file, setFile] = useState(null)

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const handleSave = async (e) => {
    e.preventDefault()
    if (!form.amount || !form.date) return
    setLoading(true)
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        category_id: form.category_id || null,
        type: typeFixed || form.type,
      }
      let saved
      if (initial?.id) {
        const res = await transactionsAPI.update(initial.id, payload)
        saved = res.data
      } else {
        const res = await transactionsAPI.create(payload)
        saved = res.data
      }
      // Загружаем чек если выбран файл
      if (file && saved.id) {
        await transactionsAPI.uploadReceipt(saved.id, file)
      }
      toast.success(initial?.id ? 'Обновлено' : 'Добавлено')
      onSave?.()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setLoading(false)
    }
  }

  const expCats = categories.filter((c) => c.is_active)

  return (
    <form onSubmit={handleSave} className="space-y-4">
      {!typeFixed && (
        <div className="flex gap-2">
          {['income', 'expense'].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => set('type', t)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all ${
                form.type === t
                  ? t === 'income'
                    ? 'bg-success-50 border-success-100 text-success-600'
                    : 'bg-danger-50 border-danger-100 text-danger-600'
                  : 'bg-white border-gray-200 text-gray-400'
              }`}
            >
              {t === 'income' ? 'Доход' : 'Расход'}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Сумма ₽"
          type="number"
          step="0.01"
          placeholder="10 000"
          value={form.amount}
          onChange={(e) => set('amount', e.target.value)}
          required
        />
        <Input
          label="Дата"
          type="date"
          value={form.date}
          onChange={(e) => set('date', e.target.value)}
          required
        />
      </div>

      {(typeFixed === 'expense' || form.type === 'expense') && (
        <Select
          label="Категория"
          value={form.category_id}
          onChange={(e) => set('category_id', e.target.value)}
        >
          <option value="">— Без категории —</option>
          {expCats.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </Select>
      )}

      <Input
        label="Описание"
        placeholder="Оплата серверов Fornex"
        value={form.description}
        onChange={(e) => set('description', e.target.value)}
      />

      <Input
        label="Ссылка на чек (Яндекс.Диск и т.д.)"
        placeholder="https://disk.yandex.ru/..."
        value={form.receipt_url}
        onChange={(e) => set('receipt_url', e.target.value)}
      />

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500">Прикрепить файл чека</label>
        <input
          type="file"
          accept="image/*,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0
                     file:text-xs file:font-medium file:bg-gray-100 file:text-gray-600
                     hover:file:bg-gray-200 cursor-pointer"
        />
      </div>

      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>
          {initial?.id ? 'Сохранить' : 'Добавить'}
        </Button>
      </div>
    </form>
  )
}

export function TransactionsPage({ typeFixed }) {
  const [items, setItems] = useState([])
  const [cats, setCats] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // null | 'add' | transaction object
  const [filters, setFilters] = useState({
    date_from: monthStart(),
    date_to: today(),
    category_id: '',
    search: '',
  })
  const { isEditor } = useAuthStore()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        type: typeFixed,
        date_from: filters.date_from,
        date_to: filters.date_to,
        limit: 200,
      }
      if (filters.category_id) params.category_id = filters.category_id
      if (filters.search) params.search = filters.search
      const [tRes, cRes] = await Promise.all([
        transactionsAPI.list(params),
        categoriesAPI.list(),
      ])
      setItems(tRes.data)
      setCats(cRes.data)
    } finally { setLoading(false) }
  }, [filters, typeFixed])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    if (!confirm('Удалить транзакцию?')) return
    try {
      await transactionsAPI.delete(id)
      toast.success('Удалено')
      load()
    } catch { toast.error('Ошибка') }
  }

  const totalIncome = items.filter((t) => t.type === 'income').reduce((s, t) => s + t.amount, 0)
  const totalExpense = items.filter((t) => t.type === 'expense').reduce((s, t) => s + t.amount, 0)

  const title = typeFixed === 'income' ? 'Доходы' : typeFixed === 'expense' ? 'Расходы' : 'Транзакции'

  return (
    <div>
      <PageHeader title={title} subtitle={`${items.length} записей за период`}>
        {isEditor() && (
          <Button variant="primary" size="sm" onClick={() => setModal('add')}>
            <Plus size={13} /> Добавить
          </Button>
        )}
      </PageHeader>

      {/* Filters */}
      <div className="flex gap-3 p-4 bg-white border-b border-gray-100 flex-wrap">
        <Input
          placeholder="Поиск..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="w-44"
        />
        <Input
          type="date"
          value={filters.date_from}
          onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
          className="w-36"
        />
        <Input
          type="date"
          value={filters.date_to}
          onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
          className="w-36"
        />
        {typeFixed !== 'income' && (
          <Select
            value={filters.category_id}
            onChange={(e) => setFilters({ ...filters, category_id: e.target.value })}
            className="w-44"
          >
            <option value="">Все категории</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        )}
        <div className="flex gap-1 ml-auto">
          <div className="text-sm text-success-600 font-medium flex items-center">
            {typeFixed !== 'expense' && `Доход: ${fmt(totalIncome)}`}
          </div>
          {!typeFixed && <span className="text-gray-200 mx-2">·</span>}
          <div className="text-sm text-danger-600 font-medium flex items-center">
            {typeFixed !== 'income' && `Расход: ${fmt(totalExpense)}`}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white">
        {loading ? (
          <div className="flex justify-center py-12"><Spinner /></div>
        ) : items.length === 0 ? (
          <Empty
            text="Нет записей за выбранный период"
            action={isEditor() && (
              <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal('add')}>
                <Plus size={13} /> Добавить первую запись
              </Button>
            )}
          />
        ) : (
          <Table headers={['Дата', 'Тип', 'Категория', 'Описание', 'Чек', 'Сумма', '']}>
            {items.map((t) => (
              <Tr key={t.id}>
                <Td className="whitespace-nowrap text-gray-400 text-xs">{fmtDate(t.date)}</Td>
                <Td>
                  <Badge variant={t.type === 'income' ? 'income' : 'expense'}>
                    {t.type === 'income' ? 'Доход' : 'Расход'}
                  </Badge>
                </Td>
                <Td>
                  {t.category && (
                    <span className="flex items-center gap-1.5 text-xs">
                      <span className="w-2 h-2 rounded-full" style={{ background: t.category.color }} />
                      {t.category.name}
                    </span>
                  )}
                </Td>
                <Td className="max-w-xs truncate text-sm">{t.description || '—'}</Td>
                <Td>
                  {(t.receipt_url || t.receipt_file) && (
                    <a
                      href={t.receipt_url || `/uploads/${t.receipt_file}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary-600 hover:underline inline-flex items-center gap-1 text-xs"
                    >
                      <Paperclip size={11} /> Чек
                    </a>
                  )}
                </Td>
                <Td>
                  <span className={`font-medium ${t.type === 'income' ? 'text-success-600' : 'text-danger-600'}`}>
                    {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
                  </span>
                </Td>
                <Td>
                  {isEditor() && (
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => setModal(t)}
                        className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        onClick={() => handleDelete(t.id)}
                        className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600 transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </div>

      {/* Add/Edit Modal */}
      <Modal
        open={!!modal}
        onClose={() => setModal(null)}
        title={modal === 'add' ? 'Добавить запись' : 'Редактировать'}
      >
        {modal && (
          <TransactionForm
            initial={modal === 'add' ? null : modal}
            categories={cats}
            typeFixed={typeFixed}
            onSave={() => { setModal(null); load() }}
            onClose={() => setModal(null)}
          />
        )}
      </Modal>
    </div>
  )
}

export default TransactionsPage
