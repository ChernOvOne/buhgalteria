import { useEffect, useState, useCallback } from 'react'
import { categoriesAPI, usersAPI, settingsAPI, milestonesAPI } from '@/api'
import { fmt, ROLE_LABELS } from '@/utils'
import { Button, Input, Select, Modal, Table, Tr, Td, Badge, Spinner, Avatar, Textarea } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Edit2, Trash2, RefreshCw, Check, X } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const PALETTE = ['#534AB7','#1D9E75','#BA7517','#E24B4A','#378ADD','#D4537E','#639922','#888780']

// ── Categories Tab ────────────────────────────────────────────────────────────
function CategoriesTab() {
  const [cats, setCats] = useState([])
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState({ name: '', color: '#534AB7', icon: '', sort_order: 0 })
  const [ruleForm, setRuleForm] = useState({ category_id: '', keyword: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const [cR, rR] = await Promise.all([categoriesAPI.list(), categoriesAPI.listRules()])
    setCats(cR.data); setRules(rR.data); setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])

  const handleSaveCat = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      if (modal?.id) await categoriesAPI.update(modal.id, form)
      else await categoriesAPI.create(form)
      toast.success(modal?.id ? 'Обновлено' : 'Категория добавлена')
      setModal(null); load()
    } catch { toast.error('Ошибка') } finally { setSaving(false) }
  }

  const handleDeleteCat = async (id) => {
    if (!confirm('Удалить категорию?')) return
    const r = await categoriesAPI.delete(id)
    toast.success(r.data.note || 'Удалено'); load()
  }

  const handleAddRule = async (e) => {
    e.preventDefault()
    if (!ruleForm.category_id || !ruleForm.keyword) return
    await categoriesAPI.createRule(ruleForm)
    toast.success('Правило добавлено')
    setRuleForm({ category_id: '', keyword: '' }); load()
  }

  const openAdd = () => { setForm({ name: '', color: '#534AB7', icon: '', sort_order: 0 }); setModal(true) }
  const openEdit = (c) => { setForm({ name: c.name, color: c.color, icon: c.icon || '', sort_order: c.sort_order }); setModal(c) }

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium">Категории расходов</div>
          <Button size="sm" variant="primary" onClick={openAdd}><Plus size={13} /> Добавить</Button>
        </div>
        <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
          <Table headers={['Цвет', 'Название', 'Статус', '']}>
            {cats.map(c => (
              <Tr key={c.id} className="group">
                <Td><span className="w-4 h-4 rounded-full block" style={{ background: c.color }} /></Td>
                <Td className="font-medium">{c.name}</Td>
                <Td><Badge variant={c.is_active ? 'success' : 'gray'}>{c.is_active ? 'Активна' : 'Скрыта'}</Badge></Td>
                <Td>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEdit(c)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"><Edit2 size={12} /></button>
                    <button onClick={() => handleDeleteCat(c.id)} className="p-1.5 rounded hover:bg-danger-50 text-gray-400 hover:text-danger-600"><Trash2 size={12} /></button>
                  </div>
                </Td>
              </Tr>
            ))}
          </Table>
        </div>
      </div>

      <div>
        <div className="text-sm font-medium mb-3">Правила автотегинга</div>
        <div className="bg-white border border-gray-100 rounded-xl p-4 space-y-3">
          <form onSubmit={handleAddRule} className="flex gap-3">
            <Select value={ruleForm.category_id} onChange={e => setRuleForm(f => ({ ...f, category_id: e.target.value }))} className="flex-1">
              <option value="">— Категория —</option>
              {cats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </Select>
            <Input value={ruleForm.keyword} onChange={e => setRuleForm(f => ({ ...f, keyword: e.target.value }))} placeholder="Ключевое слово (fornex, фнс...)" className="flex-1" />
            <Button type="submit" variant="primary" size="sm"><Plus size={13} /> Добавить</Button>
          </form>
          <div className="space-y-1">
            {rules.map(r => {
              const cat = cats.find(c => c.id === r.category_id)
              return (
                <div key={r.id} className="flex items-center gap-3 text-sm py-1.5 border-b border-gray-50 last:border-0">
                  {cat && <span className="w-2.5 h-2.5 rounded-full" style={{ background: cat.color }} />}
                  <span className="text-gray-600">{cat?.name}</span>
                  <span className="text-gray-300">→</span>
                  <code className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{r.keyword}</code>
                  <button onClick={() => categoriesAPI.deleteRule(r.id).then(load)} className="ml-auto p-1 hover:text-danger-600 text-gray-300"><X size={12} /></button>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? 'Редактировать категорию' : 'Новая категория'}
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Отмена</Button><Button variant="primary" onClick={handleSaveCat} loading={saving}>Сохранить</Button></>}>
        <div className="space-y-4">
          <Input label="Название" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required placeholder="Реклама" />
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1.5 block">Цвет</label>
            <div className="flex gap-2 flex-wrap">
              {PALETTE.map(c => (
                <button key={c} type="button" onClick={() => setForm(f => ({ ...f, color: c }))}
                  className={`w-8 h-8 rounded-full transition-all ${form.color === c ? 'ring-2 ring-offset-2 ring-gray-400 scale-110' : ''}`}
                  style={{ background: c }} />
              ))}
            </div>
          </div>
          <Input label="Порядок сортировки" type="number" value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))} />
        </div>
      </Modal>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState({ username: '', password: '', full_name: '', role: 'editor', tg_username: '', avatar_color: '#534AB7' })
  const [pwForm, setPwForm] = useState({ userId: null, password: '' })
  const [saving, setSaving] = useState(false)
  const { user: me } = useAuthStore()

  const load = () => { setLoading(true); usersAPI.list().then(r => setUsers(r.data)).finally(() => setLoading(false)) }
  useEffect(() => { load() }, [])

  const handleSave = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      if (modal?.id) await usersAPI.update(modal.id, form)
      else await usersAPI.create(form)
      toast.success(modal?.id ? 'Обновлено' : 'Пользователь создан')
      setModal(null); load()
    } catch (err) { toast.error(err.response?.data?.detail || 'Ошибка') } finally { setSaving(false) }
  }

  const handleToggle = async (u) => {
    await usersAPI.update(u.id, { is_active: !u.is_active })
    toast.success(u.is_active ? 'Деактивирован' : 'Активирован'); load()
  }

  const handlePw = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      await usersAPI.changePassword(pwForm.userId, pwForm.password)
      toast.success('Пароль изменён'); setPwForm({ userId: null, password: '' })
    } catch { toast.error('Ошибка') } finally { setSaving(false) }
  }

  const openAdd = () => { setForm({ username: '', password: '', full_name: '', role: 'editor', tg_username: '', avatar_color: '#534AB7' }); setModal(true) }
  const openEdit = (u) => { setForm({ username: u.username, password: '', full_name: u.full_name || '', role: u.role, tg_username: u.tg_username || '', avatar_color: u.avatar_color || '#534AB7' }); setModal(u) }

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-medium">{users.length} пользователей</div>
        <Button size="sm" variant="primary" onClick={openAdd}><Plus size={13} /> Создать</Button>
      </div>
      <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
        <Table headers={['Пользователь', 'Роль', 'Telegram', 'Статус', '']}>
          {users.map(u => (
            <Tr key={u.id} className="group">
              <Td>
                <div className="flex items-center gap-2.5">
                  <Avatar name={u.full_name || u.username} color={u.avatar_color} size="sm" />
                  <div>
                    <div className="text-sm font-medium">{u.full_name || u.username}</div>
                    <div className="text-xs text-gray-400">@{u.username}</div>
                  </div>
                </div>
              </Td>
              <Td><Badge variant="info">{ROLE_LABELS[u.role]}</Badge></Td>
              <Td className="text-xs text-gray-500">{u.tg_username ? `@${u.tg_username}` : '—'}</Td>
              <Td><Badge variant={u.is_active ? 'success' : 'gray'}>{u.is_active ? 'Активен' : 'Отключён'}</Badge></Td>
              <Td>
                {u.id !== me?.id && (
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEdit(u)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700"><Edit2 size={12} /></button>
                    <button onClick={() => setPwForm({ userId: u.id, password: '' })} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 text-xs">Пароль</button>
                    <button onClick={() => handleToggle(u)} className={`p-1.5 rounded text-xs ${u.is_active ? 'hover:bg-danger-50 text-gray-400 hover:text-danger-600' : 'hover:bg-success-50 text-gray-400 hover:text-success-600'}`}>
                      {u.is_active ? <X size={12} /> : <Check size={12} />}
                    </button>
                  </div>
                )}
              </Td>
            </Tr>
          ))}
        </Table>
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? 'Редактировать пользователя' : 'Новый пользователь'}
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Отмена</Button><Button variant="primary" onClick={handleSave} loading={saving}>Сохранить</Button></>}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Логин" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} required disabled={!!modal?.id} />
            {!modal?.id && <Input label="Пароль" type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />}
          </div>
          <Input label="Полное имя" value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} placeholder="Иван Иванов" />
          <Select label="Роль" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
            {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Input label="Telegram username" value={form.tg_username} onChange={e => setForm(f => ({ ...f, tg_username: e.target.value }))} placeholder="@username" />
        </div>
      </Modal>

      <Modal open={!!pwForm.userId} onClose={() => setPwForm({ userId: null, password: '' })} title="Сменить пароль"
        footer={<><Button variant="ghost" onClick={() => setPwForm({ userId: null, password: '' })}>Отмена</Button><Button variant="primary" onClick={handlePw} loading={saving}>Сохранить</Button></>}>
        <Input label="Новый пароль" type="password" value={pwForm.password} onChange={e => setPwForm(f => ({ ...f, password: e.target.value }))} required autoFocus />
      </Modal>
    </div>
  )
}

// ── App Settings Tab ──────────────────────────────────────────────────────────
function AppSettingsTab() {
  const [settings, setSettings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  useEffect(() => {
    settingsAPI.get().then(r => {
      setSettings(r.data)
      setForm({
        company_name: r.data.company_name || '',
        currency: r.data.currency || 'RUB',
        timezone: r.data.timezone || 'Europe/Moscow',
        tg_bot_token: '',
        tg_channel_id: r.data.tg_channel_id || '',
        tg_admin_id: r.data.tg_admin_id || '',
        notify_income: r.data.notify_income !== 'false',
        notify_expense: r.data.notify_expense !== 'false',
        notify_daily: r.data.notify_daily !== 'false',
        notify_monthly: r.data.notify_monthly !== 'false',
        notify_server: r.data.notify_server !== 'false',
        notify_anomaly: r.data.notify_anomaly === 'true',
      })
      setLoading(false)
    })
  }, [])

  const handleSave = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.tg_bot_token) delete payload.tg_bot_token
      await settingsAPI.update(payload)
      toast.success('Настройки сохранены')
    } catch { toast.error('Ошибка') } finally { setSaving(false) }
  }

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <div>
        <div className="text-sm font-medium mb-3">Основные</div>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Название компании / проекта" value={form.company_name} onChange={e => set('company_name', e.target.value)} />
          <Input label="Часовой пояс" value={form.timezone} onChange={e => set('timezone', e.target.value)} />
        </div>
      </div>

      <div>
        <div className="text-sm font-medium mb-3">Telegram-бот</div>
        <div className="space-y-3">
          <Input label="Токен бота (оставьте пустым чтобы не менять)" type="password" value={form.tg_bot_token} onChange={e => set('tg_bot_token', e.target.value)} placeholder="1234567890:AAF..." />
          <div className="grid grid-cols-2 gap-3">
            <Input label="ID канала для отчётов" value={form.tg_channel_id} onChange={e => set('tg_channel_id', e.target.value)} placeholder="-100123456789" />
            <Input label="Ваш Telegram ID" value={form.tg_admin_id} onChange={e => set('tg_admin_id', e.target.value)} placeholder="123456789" />
          </div>
        </div>
      </div>

      <div>
        <div className="text-sm font-medium mb-3">Уведомления</div>
        <div className="grid grid-cols-2 gap-2">
          {[
            ['notify_income',  'Новый доход'],
            ['notify_expense', 'Новый расход'],
            ['notify_daily',   'Ежедневный отчёт'],
            ['notify_monthly', 'Ежемесячный отчёт'],
            ['notify_server',  'Срок оплаты сервера'],
            ['notify_anomaly', 'Аномальный расход'],
          ].map(([k, label]) => (
            <label key={k} className="flex items-center gap-2.5 text-sm cursor-pointer py-1">
              <input type="checkbox" checked={!!form[k]} onChange={e => set(k, e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-400" />
              {label}
            </label>
          ))}
        </div>
      </div>

      <Button type="submit" variant="primary" loading={saving}>Сохранить настройки</Button>
    </form>
  )
}

// ── Milestones Tab ────────────────────────────────────────────────────────────
function MilestonesTab() {
  const [milestones, setMilestones] = useState([])
  const [form, setForm] = useState({ title: '', target_amount: '', type: 'revenue' })
  const [saving, setSaving] = useState(false)

  const load = () => milestonesAPI.list().then(r => setMilestones(r.data))
  useEffect(() => { load() }, [])

  const handleAdd = async (e) => {
    e.preventDefault(); setSaving(true)
    try {
      await milestonesAPI.create({ ...form, target_amount: parseFloat(form.target_amount) })
      toast.success('Цель добавлена'); setForm({ title: '', target_amount: '', type: 'revenue' }); load()
    } catch { toast.error('Ошибка') } finally { setSaving(false) }
  }

  const handleDelete = async (id) => { await milestonesAPI.delete(id); load() }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAdd} className="flex gap-3 items-end">
        <Input label="Название цели" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="Первый миллион выручки" required className="flex-1" />
        <Input label="Целевая сумма ₽" type="number" value={form.target_amount} onChange={e => setForm(f => ({ ...f, target_amount: e.target.value }))} required className="w-44" />
        <Select label="Тип" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))} className="w-44">
          <option value="revenue">Выручка</option>
          <option value="profit">Прибыль</option>
          <option value="investment_return">Возврат инвестиций</option>
        </Select>
        <Button type="submit" variant="primary" loading={saving}><Plus size={13} /> Добавить</Button>
      </form>

      <div className="space-y-3">
        {milestones.map(m => (
          <div key={m.id} className="bg-white border border-gray-100 rounded-xl p-4 flex items-center gap-4">
            <div className="flex-1">
              <div className="flex justify-between text-sm mb-1.5">
                <span className="font-medium">{m.title}</span>
                <span className="text-gray-400">{m.progress_percent}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full bg-primary-400 transition-all" style={{ width: `${m.progress_percent}%` }} />
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>{fmt(m.current_amount)}</span>
                <span>{fmt(m.target_amount)}</span>
              </div>
            </div>
            <button onClick={() => handleDelete(m.id)} className="p-1.5 text-gray-300 hover:text-danger-600 transition-colors"><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Audit Log Tab ─────────────────────────────────────────────────────────────
function AuditTab() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    settingsAPI.auditLog({ limit: 100 }).then(r => setLogs(r.data)).finally(() => setLoading(false))
  }, [])

  const ACTION_COLORS = { create: 'success', update: 'info', delete: 'danger', deactivate: 'warn', password_change: 'warn' }

  if (loading) return <div className="flex justify-center py-8"><Spinner /></div>

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <Table headers={['Время', 'Действие', 'Сущность', 'ID', 'Изменения']}>
        {logs.map(l => (
          <Tr key={l.id}>
            <Td className="text-xs text-gray-400 whitespace-nowrap">{new Date(l.created_at).toLocaleString('ru')}</Td>
            <Td><Badge variant={ACTION_COLORS[l.action] || 'gray'}>{l.action}</Badge></Td>
            <Td className="text-xs font-mono">{l.entity}</Td>
            <Td className="text-xs font-mono text-gray-400">{l.entity_id?.slice(0, 8)}…</Td>
            <Td className="text-xs text-gray-500 max-w-xs truncate">
              {l.new_data ? JSON.stringify(l.new_data).slice(0, 80) : '—'}
            </Td>
          </Tr>
        ))}
      </Table>
    </div>
  )
}

// ── Main Settings Page ────────────────────────────────────────────────────────
const TABS = [
  { id: 'categories', label: 'Категории' },
  { id: 'users',      label: 'Пользователи' },
  { id: 'milestones', label: 'Цели' },
  { id: 'app',        label: 'Настройки' },
  { id: 'audit',      label: 'Журнал действий' },
]

export default function SettingsPage() {
  const [tab, setTab] = useState('categories')
  const { isAdmin } = useAuthStore()

  if (!isAdmin()) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 text-sm">Нет доступа</div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Настройки" subtitle="Управление системой" />

      <div className="flex gap-0 border-b border-gray-100 bg-white px-5">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-3 text-sm transition-all ${
              tab === t.id
                ? 'text-primary-600 border-b-2 border-primary-600 font-medium'
                : 'text-gray-400 hover:text-gray-600'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-5">
        {tab === 'categories' && <CategoriesTab />}
        {tab === 'users'      && <UsersTab />}
        {tab === 'milestones' && <MilestonesTab />}
        {tab === 'app'        && <AppSettingsTab />}
        {tab === 'audit'      && <AuditTab />}
      </div>
    </div>
  )
}
