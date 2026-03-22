import { useEffect, useState, useCallback } from 'react'
import { adsAPI, partnersAPI, utmAPI } from '@/api'
import { fmt, fmtDate, today, monthStart } from '@/utils'
import { Button, Input, Select, Modal, Table, Tr, Td, Badge, Empty, Spinner, Textarea } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Edit2, Trash2, Copy, Link, ExternalLink } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  date: today(), channel_name: '', channel_url: '',
  format: '', amount: '', subscribers_gained: '', screenshot_url: '', notes: '',
  budget_source: 'account', investor_partner_id: '',
  target_url: '', target_type: 'bot',
}

// ── UTM ссылки попап ──────────────────────────────────────────────────────────
function UtmLinksModal({ campaign, onClose }) {
  const base = window.location.origin
  const utmUrl = `${base}/go/${campaign.utm_code}`

  const copy = (text, label) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text)
        .then(() => toast.success(`${label} скопировано`))
        .catch(() => toast.error('Не удалось скопировать'))
    } else {
      // fallback
      const el = document.createElement('textarea')
      el.value = text
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      toast.success(`${label} скопировано`)
    }
  }

  return (
    <Modal open onClose={onClose} title="Кампания создана — UTM ссылки" size="md">
      <div className="space-y-4">

        <div className="p-3 bg-success-50 border border-success-100 rounded-xl text-sm text-success-600">
          Используйте эту ссылку в рекламе вместо прямой ссылки на бота/канал
        </div>

        {/* Main UTM link */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">
            Короткая UTM-ссылка (вставляйте в рекламу)
          </div>
          <div className="flex items-center gap-2 bg-gray-50 rounded-xl p-3 border border-gray-100">
            <Link size={14} className="text-primary-500 flex-shrink-0" />
            <code className="text-sm font-mono flex-1 text-primary-600 break-all">{utmUrl}</code>
            <button
              onClick={() => copy(utmUrl, 'Ссылка')}
              className="flex-shrink-0 px-3 py-1.5 bg-primary-600 text-white rounded-lg text-xs font-medium hover:bg-primary-700 flex items-center gap-1"
            >
              <Copy size={11} /> Копировать
            </button>
          </div>
          {campaign.target_url && (
            <div className="text-xs text-gray-400 mt-1.5 flex items-center gap-1">
              <span>Ведёт на:</span>
              <span className="font-mono text-gray-500 truncate">{campaign.target_url}</span>
            </div>
          )}
        </div>

        {/* UTM code for LEADTEH */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">
            UTM код (для LEADTEH — параметр при старте сценария)
          </div>
          <div className="flex items-center gap-2 bg-gray-50 rounded-xl p-3 border border-gray-100">
            <code className="text-sm font-mono flex-1 text-warn-600">{campaign.utm_code}</code>
            <button
              onClick={() => copy(campaign.utm_code, 'UTM код')}
              className="flex-shrink-0 px-3 py-1.5 bg-warn-600 text-white rounded-lg text-xs font-medium hover:bg-warn-700 flex items-center gap-1"
            >
              <Copy size={11} /> Копировать
            </button>
          </div>
        </div>

        <div className="bg-primary-50 border border-primary-100 rounded-xl p-4 text-xs text-primary-600 space-y-1">
          <div className="font-medium mb-1.5">Как использовать:</div>
          <div>1. UTM-ссылку вставьте в рекламный пост</div>
          <div>2. UTM код зашейте в LEADTEH как стартовый параметр</div>
          <div>3. При входе пользователя LEADTEH шлёт POST /api/utm/lead</div>
          <div>4. При оплате LEADTEH шлёт POST /api/payments/webhook</div>
          <div className="mt-2 text-gray-400">Инструкция: Настройки → Документация API</div>
        </div>

        <div className="flex justify-end">
          <Button variant="primary" onClick={onClose}>Готово</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── AdForm ────────────────────────────────────────────────────────────────────
function AdForm({ initial, onSave, onClose, partners = [] }) {
  const [form, setForm] = useState(initial ? {
    ...initial,
    amount: initial.amount ?? '',
    subscribers_gained: initial.subscribers_gained ?? '',
    budget_source: initial.budget_source || 'account',
    investor_partner_id: initial.investor_partner_id || '',
    target_url: initial.target_url || '',
    target_type: initial.target_type || 'bot',
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
      if (initial?.id) {
        await adsAPI.update(initial.id, payload)
        toast.success('Обновлено')
        onSave?.()
      } else {
        const res = await adsAPI.create(payload)
        toast.success('Кампания создана')
        onSave?.(res.data)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input label="Дата" type="date" value={form.date} onChange={e => set('date', e.target.value)} required />
        <Input label="Формат" value={form.format} onChange={e => set('format', e.target.value)} placeholder="2/48, 1/24" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Название канала" value={form.channel_name} onChange={e => set('channel_name', e.target.value)} placeholder="TikTok Updates" required />
        <Input label="Ссылка на канал" value={form.channel_url} onChange={e => set('channel_url', e.target.value)} placeholder="https://t.me/..." />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input label="Сумма ₽" type="number" step="0.01" value={form.amount} onChange={e => set('amount', e.target.value)} required placeholder="10000" />
        <Input label="Привлечено ПДП" type="number" value={form.subscribers_gained} onChange={e => set('subscribers_gained', e.target.value)} placeholder="1234" />
      </div>

      {/* Target URL для UTM */}
      <div>
        <div className="text-xs font-medium text-gray-500 mb-2">
          Целевая ссылка — куда переходит пользователь после клика
        </div>
        <div className="flex gap-2 mb-2">
          {[
            { value: 'bot',     label: 'Бот' },
            { value: 'channel', label: 'Канал' },
            { value: 'custom',  label: 'Другое' },
          ].map(opt => (
            <button key={opt.value} type="button"
              onClick={() => set('target_type', opt.value)}
              className={`px-3 py-1 rounded-xl text-xs font-medium transition-all ${
                form.target_type === opt.value ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {opt.label}
            </button>
          ))}
        </div>
        <Input
          value={form.target_url}
          onChange={e => set('target_url', e.target.value)}
          placeholder={
            form.target_type === 'bot'     ? 'https://t.me/your_vpn_bot' :
            form.target_type === 'channel' ? 'https://t.me/your_channel' :
            'https://example.com'
          }
        />
        <div className="text-xs text-gray-400 mt-1">
          Система создаст короткую UTM-ссылку которая будет вести сюда и считать клики
        </div>
      </div>

      <Textarea label="Заметки" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} />

      {/* Budget source */}
      <div>
        <label className="text-xs font-medium text-gray-500 mb-2 block">Источник бюджета</label>
        <div className="flex gap-2 flex-wrap">
          {[
            { value: 'account',    label: 'Со счёта' },
            { value: 'investment', label: 'Инвестиция партнёра' },
            { value: 'stats_only', label: 'Только статистика' },
          ].map(opt => (
            <button key={opt.value} type="button"
              onClick={() => set('budget_source', opt.value)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                form.budget_source === opt.value ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {opt.label}
            </button>
          ))}
        </div>
        {form.budget_source === 'investment' && (
          <Select
            label="Партнёр-инвестор"
            value={form.investor_partner_id}
            onChange={e => set('investor_partner_id', e.target.value)}
            className="mt-3"
          >
            <option value="">— Выберите партнёра —</option>
            {partners.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </Select>
        )}
        <div className="text-xs text-gray-400 mt-1">
          {form.budget_source === 'account'    && 'Спишется со счёта как расход'}
          {form.budget_source === 'investment' && 'Записывается как долг перед партнёром'}
          {form.budget_source === 'stats_only' && 'Только для учёта ROI, ничего не списывается'}
        </div>
      </div>

      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>
          {initial?.id ? 'Сохранить' : 'Создать кампанию'}
        </Button>
      </div>
    </form>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AdsPage() {
  const [campaigns, setCampaigns] = useState([])
  const [summary, setSummary]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [modal, setModal]         = useState(null)
  const [utmModal, setUtmModal]   = useState(null)
  const [partners, setPartners]   = useState([])
  const [filters, setFilters]     = useState({ date_from: monthStart(), date_to: today() })
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

  useEffect(() => {
    load()
    partnersAPI.list().then(r => setPartners(r.data)).catch(() => {})
  }, [load])

  const handleDelete = async (id) => {
    if (!confirm('Удалить кампанию?')) return
    await adsAPI.delete(id)
    toast.success('Удалено')
    load()
  }

  const copyUtmLink = (campaign) => {
    const url = `${window.location.origin}/go/${campaign.utm_code}`
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url)
        .then(() => toast.success('UTM ссылка скопирована'))
        .catch(() => toast.error('Не удалось скопировать'))
    } else {
      const el = document.createElement('textarea')
      el.value = url
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      toast.success('UTM ссылка скопирована')
    }
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 p-3 md:p-5 pb-0">
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
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 p-3 md:p-5 pb-0 flex-wrap">
        <Input type="date" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))} className="w-36" />
        <Input type="date" value={filters.date_to}   onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))}   className="w-36" />
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
            <Table headers={['Дата', 'Канал', 'Бюджет', 'Сумма', 'ПДП', '₽/ПДП', 'UTM ссылка', '']}>
              {campaigns.map(c => (
                <Tr key={c.id} className="group">
                  <Td className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(c.date)}</Td>
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
                  <Td>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                      c.budget_source === 'investment' ? 'bg-warn-50 text-warn-600' :
                      c.budget_source === 'stats_only' ? 'bg-gray-100 text-gray-400' :
                      'bg-success-50 text-success-600'
                    }`}>
                      {c.budget_source === 'investment' ? 'Инвест.' : c.budget_source === 'stats_only' ? 'Статист.' : 'Счёт'}
                    </span>
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

                  {/* UTM ссылка — видна всегда */}
                  <Td>
                    {c.utm_code ? (
                      <div className="flex items-center gap-1.5">
                        <code className="text-xs font-mono text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded">
                          /go/{c.utm_code}
                        </code>
                        <button
                          onClick={() => copyUtmLink(c)}
                          title="Копировать UTM ссылку"
                          className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-primary-600 transition-colors"
                        >
                          <Copy size={12} />
                        </button>
                        <button
                          onClick={() => setUtmModal(c)}
                          title="Показать все ссылки"
                          className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-primary-600 transition-colors"
                        >
                          <Link size={12} />
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-300">нет</span>
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

      {modal && (
        <Modal open onClose={() => setModal(null)} title={modal === 'add' ? 'Новая кампания' : 'Редактировать кампанию'} size="lg">
          <AdForm
            initial={modal === 'add' ? null : modal}
            onSave={(newCampaign) => {
              setModal(null)
              load()
              if (newCampaign?.utm_code) setUtmModal(newCampaign)
            }}
            onClose={() => setModal(null)}
            partners={partners}
          />
        </Modal>
      )}

      {utmModal && (
        <UtmLinksModal campaign={utmModal} onClose={() => setUtmModal(null)} />
      )}
    </div>
  )
}
