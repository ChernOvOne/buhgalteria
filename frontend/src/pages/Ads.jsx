import { useEffect, useState, useCallback } from 'react'
import { adsAPI, partnersAPI } from '@/api'
import { fmt, fmtDate, today, monthStart } from '@/utils'
import { Button, Input, Select, Modal, Textarea, Empty, Spinner, KpiCard } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { Plus, Edit2, Trash2, Copy, Link, ExternalLink, ChevronDown, ChevronUp, BookOpen } from 'lucide-react'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'

const EMPTY_FORM = {
  date: today(), channel_name: '', channel_url: '',
  format: '', amount: '', subscribers_gained: '', screenshot_url: '', notes: '',
  budget_source: 'account', investor_partner_id: '',
  target_url: '', target_type: 'bot',
}

function UtmLinksModal({ campaign, onClose }) {
  const base = window.location.origin
  const utmUrl = `${base}/go/${campaign.utm_code}`
  const apiUrl = `${base}/api/utm/lead`
  const copy = (text, label) => {
    navigator.clipboard?.writeText(text).then(() => toast.success(`${label} скопировано`))
      .catch(() => { const el = document.createElement('textarea'); el.value = text; document.body.appendChild(el); el.select(); document.execCommand('copy'); document.body.removeChild(el); toast.success(`${label} скопировано`) })
  }
  const webhookJson = JSON.stringify({ utm_code: campaign.utm_code, customer_id: "{{telegram_id}}", customer_name: "{{first_name}} {{last_name}}", username: "{{username}}", extra_data: { source: "leadtex" } }, null, 2)

  return (
    <Modal open onClose={onClose} title="UTM ссылки и интеграция LEADTEX" size="lg">
      <div className="space-y-4">
        <div className="p-3 bg-success-50 border border-success-100 rounded-xl text-sm text-success-600">Используйте эту ссылку в рекламе вместо прямой ссылки на бота</div>
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">Короткая UTM-ссылка</div>
          <div className="flex items-center gap-2 bg-gray-50 rounded-xl p-3 border border-gray-100">
            <Link size={14} className="text-primary-500 flex-shrink-0" />
            <code className="text-sm font-mono flex-1 text-primary-600 break-all">{utmUrl}</code>
            <button onClick={() => copy(utmUrl, 'Ссылка')} className="flex-shrink-0 px-3 py-1.5 bg-primary-600 text-white rounded-lg text-xs font-medium hover:bg-primary-800 flex items-center gap-1"><Copy size={11} /> Копировать</button>
          </div>
        </div>
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">UTM код</div>
          <div className="flex items-center gap-2 bg-gray-50 rounded-xl p-3 border border-gray-100">
            <code className="text-sm font-mono flex-1 text-warn-600">{campaign.utm_code}</code>
            <button onClick={() => copy(campaign.utm_code, 'UTM код')} className="flex-shrink-0 px-3 py-1.5 bg-warn-600 text-white rounded-lg text-xs font-medium hover:bg-warn-700 flex items-center gap-1"><Copy size={11} /> Копировать</button>
          </div>
        </div>
        <div className="bg-primary-50 border border-primary-100 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3"><BookOpen size={14} className="text-primary-600" /><div className="text-xs font-medium text-primary-600">Инструкция для LEADTEX</div></div>
          <div className="space-y-3 text-xs text-primary-600">
            <div><div className="font-medium mb-1">1. Блок «Старт»:</div><div className="text-gray-500">Сохраните параметр /start в переменную <code className="bg-white px-1 rounded">utm_code</code></div></div>
            <div>
              <div className="font-medium mb-1">2. Блок «Исходящий Webhook»:</div>
              <div className="text-gray-500 mb-1">URL: POST</div>
              <div className="flex items-center gap-2 bg-white rounded-lg p-2 border border-primary-100">
                <code className="text-xs font-mono flex-1 text-gray-700 break-all">{apiUrl}</code>
                <button onClick={() => copy(apiUrl, 'URL')} className="text-primary-600"><Copy size={11} /></button>
              </div>
              <div className="text-gray-500 mt-2 mb-1">JSON тело:</div>
              <div className="relative bg-white rounded-lg p-2 border border-primary-100">
                <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap">{webhookJson}</pre>
                <button onClick={() => copy(webhookJson, 'JSON')} className="absolute top-1 right-1 p-1 text-primary-600"><Copy size={11} /></button>
              </div>
            </div>
            <div><div className="font-medium mb-1">3. При оплате — Webhook на:</div><div className="text-gray-500"><code className="bg-white px-1 rounded">{base}/api/payments/webhook</code></div></div>
          </div>
        </div>
        <div className="flex justify-end"><Button variant="primary" onClick={onClose}>Готово</Button></div>
      </div>
    </Modal>
  )
}

function FunnelBar({ clicks, leads, converted, revenue }) {
  const maxVal = Math.max(clicks, 1)
  const items = [
    { label: 'Клики', value: clicks, color: 'bg-gray-300' },
    { label: 'Лиды', value: leads, color: 'bg-primary-400', pct: clicks > 0 ? Math.round(leads / clicks * 100) : 0 },
    { label: 'Оплаты', value: converted, color: 'bg-success-600', pct: leads > 0 ? Math.round(converted / leads * 100) : 0 },
  ]
  return (
    <div className="flex items-end gap-3">
      {items.map((item, i) => (
        <div key={i} className="flex-1 text-center">
          <div className="text-lg font-medium">{item.value}</div>
          <div className="text-xs text-gray-400 mb-1">{item.label}{item.pct > 0 && <span className="text-primary-600 ml-1">({item.pct}%)</span>}</div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden"><div className={`h-full rounded-full ${item.color} transition-all`} style={{ width: `${Math.max(2, item.value / maxVal * 100)}%` }} /></div>
        </div>
      ))}
      {revenue > 0 && <div className="flex-1 text-center"><div className="text-lg font-medium text-success-600">{fmt(revenue)}</div><div className="text-xs text-gray-400 mb-1">Выручка</div><div className="h-2 bg-success-50 rounded-full" /></div>}
    </div>
  )
}

function CampaignCard({ campaign, funnel, onEdit, onDelete, onShowUtm, isEditor }) {
  const [expanded, setExpanded] = useState(false)
  const f = funnel || {}
  const copyUtm = () => { navigator.clipboard?.writeText(`${window.location.origin}/go/${campaign.utm_code}`).then(() => toast.success('UTM скопирована')) }

  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <div className="p-3 md:p-4 cursor-pointer hover:bg-gray-50/50 transition-colors" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {campaign.channel_url ? (
                <a href={campaign.channel_url} target="_blank" rel="noreferrer" className="text-sm font-medium text-primary-600 hover:underline flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  {campaign.channel_name || '—'} <ExternalLink size={10} />
                </a>
              ) : <span className="text-sm font-medium">{campaign.channel_name || '—'}</span>}
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${campaign.budget_source === 'investment' ? 'bg-warn-50 text-warn-600' : campaign.budget_source === 'stats_only' ? 'bg-gray-100 text-gray-400' : 'bg-success-50 text-success-600'}`}>
                {campaign.budget_source === 'investment' ? 'Инвест.' : campaign.budget_source === 'stats_only' ? 'Стат.' : 'Счёт'}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
              <span>{fmtDate(campaign.date)}</span>
              <span className="font-medium text-gray-600">{fmt(campaign.amount)}</span>
              {campaign.subscribers_gained > 0 && <span>{campaign.subscribers_gained} ПДП</span>}
              {campaign.utm_code && <span className="font-mono text-primary-500 hidden md:inline">/go/{campaign.utm_code}</span>}
            </div>
          </div>
          <div className="hidden md:flex items-center gap-4 text-center">
            <div><div className="text-sm font-medium">{f.clicks || 0}</div><div className="text-xs text-gray-400">клики</div></div>
            <div><div className="text-sm font-medium">{f.leads || 0}</div><div className="text-xs text-gray-400">лиды</div></div>
            <div><div className="text-sm font-medium text-success-600">{f.converted || 0}</div><div className="text-xs text-gray-400">оплаты</div></div>
            {f.roi !== 0 && f.roi !== undefined && <div><div className={`text-sm font-medium ${f.roi > 0 ? 'text-success-600' : 'text-danger-600'}`}>{f.roi > 0 ? '+' : ''}{f.roi}%</div><div className="text-xs text-gray-400">ROI</div></div>}
          </div>
          <div className="flex items-center gap-1">
            {campaign.utm_code && <button onClick={e => { e.stopPropagation(); copyUtm() }} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-primary-600" title="Копировать UTM"><Copy size={12} /></button>}
            {campaign.utm_code && <button onClick={e => { e.stopPropagation(); onShowUtm(campaign) }} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-primary-600" title="LEADTEX"><BookOpen size={12} /></button>}
            {expanded ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
          </div>
        </div>
      </div>
      {expanded && (
        <div className="px-3 md:px-4 pb-3 md:pb-4 border-t border-gray-50 pt-3 space-y-3">
          <FunnelBar clicks={f.clicks || 0} leads={f.leads || 0} converted={f.converted || 0} revenue={f.revenue || 0} />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="bg-gray-50 rounded-lg p-2.5"><div className="text-xs text-gray-400 mb-0.5">CPA</div><div className="text-sm font-medium">{f.cpa ? fmt(f.cpa) : '—'}</div></div>
            <div className="bg-gray-50 rounded-lg p-2.5"><div className="text-xs text-gray-400 mb-0.5">Цена ПДП</div><div className="text-sm font-medium">{campaign.cost_per_sub ? fmt(campaign.cost_per_sub) : '—'}</div></div>
            <div className="bg-gray-50 rounded-lg p-2.5"><div className="text-xs text-gray-400 mb-0.5">Выручка</div><div className="text-sm font-medium text-success-600">{f.revenue ? fmt(f.revenue) : '—'}</div></div>
            <div className="bg-gray-50 rounded-lg p-2.5"><div className="text-xs text-gray-400 mb-0.5">LTV</div><div className="text-sm font-medium">{f.ltv ? fmt(f.ltv) : '—'}</div></div>
          </div>
          {isEditor && <div className="flex gap-2 pt-1">
            <Button size="sm" variant="ghost" onClick={() => onEdit(campaign)}><Edit2 size={12} /> Редактировать</Button>
            <Button size="sm" variant="danger" onClick={() => onDelete(campaign.id)}><Trash2 size={12} /> Удалить</Button>
          </div>}
        </div>
      )}
    </div>
  )
}

function AdForm({ initial, onSave, onClose, partners = [] }) {
  const [form, setForm] = useState(initial ? { ...initial, amount: initial.amount ?? '', subscribers_gained: initial.subscribers_gained ?? '', budget_source: initial.budget_source || 'account', investor_partner_id: initial.investor_partner_id || '', target_url: initial.target_url || '', target_type: initial.target_type || 'bot' } : { ...EMPTY_FORM })
  const [loading, setLoading] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const handleSave = async (e) => {
    e.preventDefault(); setLoading(true)
    try {
      const payload = { ...form, amount: parseFloat(form.amount), subscribers_gained: form.subscribers_gained !== '' ? parseInt(form.subscribers_gained) : null }
      if (initial?.id) { await adsAPI.update(initial.id, payload); toast.success('Обновлено'); onSave?.() }
      else { const res = await adsAPI.create(payload); toast.success('Кампания создана'); onSave?.(res.data) }
    } catch (err) { toast.error(err.response?.data?.detail || 'Ошибка') }
    finally { setLoading(false) }
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
        <Input label="Сумма" type="number" step="0.01" value={form.amount} onChange={e => set('amount', e.target.value)} required />
        <Input label="Привлечено ПДП" type="number" value={form.subscribers_gained} onChange={e => set('subscribers_gained', e.target.value)} />
      </div>
      <div>
        <div className="text-xs font-medium text-gray-500 mb-2">Целевая ссылка</div>
        <div className="flex gap-2 mb-2">
          {[{ value: 'bot', label: 'Бот' }, { value: 'channel', label: 'Канал' }, { value: 'custom', label: 'Другое' }].map(opt => (
            <button key={opt.value} type="button" onClick={() => set('target_type', opt.value)} className={`px-3 py-1 rounded-xl text-xs font-medium transition-all ${form.target_type === opt.value ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>{opt.label}</button>
          ))}
        </div>
        <Input value={form.target_url} onChange={e => set('target_url', e.target.value)} placeholder={form.target_type === 'bot' ? 'https://t.me/your_vpn_bot' : form.target_type === 'channel' ? 'https://t.me/your_channel' : 'https://example.com'} />
      </div>
      <Textarea label="Заметки" value={form.notes} onChange={e => set('notes', e.target.value)} rows={2} />
      <div>
        <label className="text-xs font-medium text-gray-500 mb-2 block">Источник бюджета</label>
        <div className="flex gap-2 flex-wrap">
          {[{ value: 'account', label: 'Со счёта' }, { value: 'investment', label: 'Инвестиция партнёра' }, { value: 'stats_only', label: 'Только статистика' }].map(opt => (
            <button key={opt.value} type="button" onClick={() => set('budget_source', opt.value)} className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${form.budget_source === opt.value ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>{opt.label}</button>
          ))}
        </div>
        {form.budget_source === 'investment' && <Select label="Партнёр-инвестор" value={form.investor_partner_id} onChange={e => set('investor_partner_id', e.target.value)} className="mt-3"><option value="">— Выберите —</option>{partners.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Select>}
      </div>
      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
        <Button type="submit" variant="primary" loading={loading}>{initial?.id ? 'Сохранить' : 'Создать кампанию'}</Button>
      </div>
    </form>
  )
}

export default function AdsPage() {
  const [campaigns, setCampaigns] = useState([])
  const [funnel, setFunnel] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null)
  const [utmModal, setUtmModal] = useState(null)
  const [partners, setPartners] = useState([])
  const [filters, setFilters] = useState({ date_from: monthStart(), date_to: today() })
  const { isEditor } = useAuthStore()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [camRes, funnelRes] = await Promise.all([adsAPI.list(filters), adsAPI.funnel(filters)])
      setCampaigns(camRes.data)
      setFunnel(funnelRes.data)
    } catch { toast.error('Ошибка загрузки') }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { load(); partnersAPI.list().then(r => setPartners(r.data)).catch(() => {}) }, [load])

  const handleDelete = async (id) => { if (!confirm('Удалить кампанию?')) return; await adsAPI.delete(id); toast.success('Удалено'); load() }

  const funnelMap = {}
  if (funnel?.campaigns) funnel.campaigns.forEach(f => { funnelMap[f.id] = f })

  return (
    <div>
      <PageHeader title="Маркетинг" subtitle="Рекламные кампании и воронка конверсий">
        {isEditor() && <Button variant="primary" size="sm" onClick={() => setModal('add')}><Plus size={13} /> Новая кампания</Button>}
      </PageHeader>

      {funnel?.totals && (
        <div className="p-3 md:p-5 pb-0">
          <div className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-xs font-medium text-gray-500 mb-3">Общая воронка за период</div>
            <FunnelBar clicks={funnel.totals.clicks} leads={funnel.totals.leads} converted={funnel.totals.converted} revenue={funnel.totals.revenue} />
            <div className="flex gap-3 mt-3 flex-wrap">
              <div className="text-xs text-gray-400">Потрачено: <span className="font-medium text-gray-600">{fmt(funnel.totals.spent)}</span></div>
              <div className="text-xs text-gray-400">ROI: <span className={`font-medium ${funnel.totals.roi > 0 ? 'text-success-600' : 'text-danger-600'}`}>{funnel.totals.roi > 0 ? '+' : ''}{funnel.totals.roi}%</span></div>
              <div className="text-xs text-gray-400">Клик→Лид: <span className="font-medium text-primary-600">{funnel.totals.click_to_lead}%</span></div>
              <div className="text-xs text-gray-400">Лид→Оплата: <span className="font-medium text-success-600">{funnel.totals.lead_to_pay}%</span></div>
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-2 p-3 md:p-5 pb-0 flex-wrap">
        <Input type="date" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))} className="w-36" />
        <Input type="date" value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))} className="w-36" />
      </div>

      <div className="p-3 md:p-5 space-y-2">
        {loading ? <div className="flex justify-center py-12"><Spinner /></div>
        : campaigns.length === 0 ? <Empty text="Кампаний не найдено" action={isEditor() && <Button variant="primary" size="sm" className="mt-3" onClick={() => setModal('add')}><Plus size={13} />Добавить</Button>} />
        : campaigns.map(c => <CampaignCard key={c.id} campaign={c} funnel={funnelMap[c.id]} onEdit={setModal} onDelete={handleDelete} onShowUtm={setUtmModal} isEditor={isEditor()} />)}
      </div>

      {modal && <Modal open onClose={() => setModal(null)} title={modal === 'add' ? 'Новая кампания' : 'Редактировать'} size="lg">
        <AdForm initial={modal === 'add' ? null : modal} onSave={(nc) => { setModal(null); load(); if (nc?.utm_code) setUtmModal(nc) }} onClose={() => setModal(null)} partners={partners} />
      </Modal>}
      {utmModal && <UtmLinksModal campaign={utmModal} onClose={() => setUtmModal(null)} />}
    </div>
  )
}
