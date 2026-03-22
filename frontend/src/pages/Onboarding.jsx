import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { categoriesAPI, settingsAPI } from '@/api'
import { Button, Input, Select, Textarea } from '@/components/ui'
import { useAuthStore } from '@/store'
import toast from 'react-hot-toast'
import { Check, Plus, X } from 'lucide-react'

const DEFAULT_CATS = [
  { name: 'Реклама',   color: '#534AB7' },
  { name: 'Сервера',   color: '#1D9E75' },
  { name: 'LeadTex',   color: '#639922' },
  { name: 'ФНС',       color: '#BA7517' },
  { name: 'ТГ Прем',   color: '#378ADD' },
  { name: 'СКАМ',      color: '#E24B4A' },
]
const PALETTE = ['#534AB7','#1D9E75','#BA7517','#E24B4A','#378ADD','#D4537E','#639922','#888780']

const STEPS = ['Компания', 'Категории', 'Партнёры', 'Финансы', 'Telegram']

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { fetchMe } = useAuthStore()
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)

  const [data, setData] = useState({
    company_name: 'Мой бизнес',
    currency: 'RUB',
    timezone: 'Europe/Moscow',
    starting_balance: '',
    historical_income: '',
    historical_expense: '',
    total_investments: '',
    total_returned: '',
    total_dividends: '',
    accounting_start_month: '',
    tg_bot_token: '',
    tg_channel_id: '',
    tg_admin_id: '',
  })

  const [cats, setCats] = useState(DEFAULT_CATS.map(c => ({ ...c })))
  const [partners, setPartners] = useState([
    { name: '', role_label: 'Партнёр', tg_username: '', initial_investment: '', initial_returned: '', initial_dividends: '' },
  ])

  const setD = (k, v) => setData(d => ({ ...d, [k]: v }))

  const addCat = () => setCats(c => [...c, { name: '', color: '#534AB7' }])
  const delCat = (i) => setCats(c => c.filter((_, idx) => idx !== i))
  const setCat = (i, k, v) => setCats(c => c.map((cat, idx) => idx === i ? { ...cat, [k]: v } : cat))

  const addPartner = () => setPartners(p => [...p, { name: '', role_label: 'Партнёр', tg_username: '', initial_investment: '', initial_returned: '', initial_dividends: '' }])
  const delPartner = (i) => setPartners(p => p.filter((_, idx) => idx !== i))
  const setPartner = (i, k, v) => setPartners(p => p.map((pt, idx) => idx === i ? { ...pt, [k]: v } : pt))

  const handleFinish = async () => {
    setSaving(true)
    try {
      const payload = {
        ...data,
        starting_balance: parseFloat(data.starting_balance) || 0,
        historical_income: parseFloat(data.historical_income) || 0,
        historical_expense: parseFloat(data.historical_expense) || 0,
        total_investments: parseFloat(data.total_investments) || 0,
        total_returned: parseFloat(data.total_returned) || 0,
        total_dividends: parseFloat(data.total_dividends) || 0,
        categories: cats.filter(c => c.name).map(c => ({ name: c.name, color: c.color })),
        partners: partners.filter(p => p.name).map(p => ({
          ...p,
          initial_investment: parseFloat(p.initial_investment) || 0,
          initial_returned: parseFloat(p.initial_returned) || 0,
          initial_dividends: parseFloat(p.initial_dividends) || 0,
        })),
      }
      await settingsAPI.onboarding(payload)
      toast.success('Настройка завершена!')
      await fetchMe()
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения')
    } finally { setSaving(false) }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="bg-white border border-gray-100 rounded-2xl w-full max-w-2xl shadow-sm overflow-hidden">

        {/* Header */}
        <div className="px-8 pt-7 pb-5 border-b border-gray-100">
          <div className="text-lg font-medium mb-5">Первоначальная настройка</div>
          <div className="flex items-center gap-0">
            {STEPS.map((s, i) => (
              <div key={i} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center">
                  <div
                    onClick={() => i < step && setStep(i)}
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all
                      ${i < step ? 'bg-success-600 text-white cursor-pointer' : i === step ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-400'}`}
                  >
                    {i < step ? <Check size={12} /> : i + 1}
                  </div>
                  <div className={`text-xs mt-1 ${i === step ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>{s}</div>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-px mx-2 mb-4 ${i < step ? 'bg-success-600' : 'bg-gray-100'}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="px-8 py-6 min-h-64">

          {step === 0 && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Input label="Название проекта" value={data.company_name} onChange={e => setD('company_name', e.target.value)} placeholder="TikMod Business" />
                <Select label="Валюта" value={data.currency} onChange={e => setD('currency', e.target.value)}>
                  <option value="RUB">RUB (₽)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                </Select>
              </div>
              <Select label="Часовой пояс" value={data.timezone} onChange={e => setD('timezone', e.target.value)}>
                <option value="Europe/Moscow">Europe/Moscow (UTC+3)</option>
                <option value="Europe/Kaliningrad">Europe/Kaliningrad (UTC+2)</option>
                <option value="Asia/Yekaterinburg">Asia/Yekaterinburg (UTC+5)</option>
              </Select>
              <Input label="Текущий остаток на счёте ₽" type="number" value={data.starting_balance} onChange={e => setD('starting_balance', e.target.value)} placeholder="35345" />
            </div>
          )}

          {step === 1 && (
            <div>
              <div className="space-y-2 mb-3">
                {cats.map((c, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl bg-gray-50">
                    <div className="flex gap-1.5">
                      {PALETTE.map(clr => (
                        <button key={clr} type="button" onClick={() => setCat(i, 'color', clr)}
                          className={`w-5 h-5 rounded-full transition-all ${c.color === clr ? 'ring-2 ring-offset-1 ring-gray-400' : ''}`}
                          style={{ background: clr }} />
                      ))}
                    </div>
                    <input
                      value={c.name} onChange={e => setCat(i, 'name', e.target.value)}
                      placeholder="Название категории"
                      className="flex-1 text-sm bg-transparent outline-none border-none"
                    />
                    <button onClick={() => delCat(i)} className="p-1 text-gray-300 hover:text-danger-600 transition-colors"><X size={14} /></button>
                  </div>
                ))}
              </div>
              <button onClick={addCat} className="text-sm text-primary-600 hover:text-primary-800 flex items-center gap-1.5 transition-colors">
                <Plus size={14} /> Добавить категорию
              </button>
            </div>
          )}

          {step === 2 && (
            <div>
              <div className="space-y-4 mb-4">
                {partners.map((p, i) => (
                  <div key={i} className="p-4 border border-gray-100 rounded-xl bg-gray-50">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="grid grid-cols-2 gap-3 flex-1">
                        <Input label="Имя" value={p.name} onChange={e => setPartner(i, 'name', e.target.value)} placeholder="Артём" />
                        <Select label="Роль" value={p.role_label} onChange={e => setPartner(i, 'role_label', e.target.value)}>
                          <option>Партнёр</option><option>Инвестор</option>
                        </Select>
                      </div>
                      <button onClick={() => delPartner(i)} className="p-1.5 mt-4 text-gray-300 hover:text-danger-600 transition-colors"><X size={14} /></button>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <Input label="Вложено ₽" type="number" value={p.initial_investment} onChange={e => setPartner(i, 'initial_investment', e.target.value)} placeholder="0" />
                      <Input label="Возвращено ₽" type="number" value={p.initial_returned} onChange={e => setPartner(i, 'initial_returned', e.target.value)} placeholder="0" />
                      <Input label="ДВД выплачено ₽" type="number" value={p.initial_dividends} onChange={e => setPartner(i, 'initial_dividends', e.target.value)} placeholder="0" />
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={addPartner} className="text-sm text-primary-600 hover:text-primary-800 flex items-center gap-1.5 transition-colors">
                <Plus size={14} /> Добавить партнёра
              </button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="p-3 bg-primary-50 rounded-xl text-sm text-primary-600">
                Введи итоговые цифры из Excel — они лягут в базу как исторические данные и будут учитываться в общей статистике.
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input label="Выручка до старта системы ₽" type="number" value={data.historical_income} onChange={e => setD('historical_income', e.target.value)} placeholder="577372" />
                <Input label="Расходы до старта системы ₽" type="number" value={data.historical_expense} onChange={e => setD('historical_expense', e.target.value)} placeholder="512984" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Input label="Всего вложено инвестиций ₽" type="number" value={data.total_investments} onChange={e => setD('total_investments', e.target.value)} placeholder="860285" />
                <Input label="Возвращено инвестиций ₽" type="number" value={data.total_returned} onChange={e => setD('total_returned', e.target.value)} placeholder="641135" />
                <Input label="Выплачено ДВД всего ₽" type="number" value={data.total_dividends} onChange={e => setD('total_dividends', e.target.value)} placeholder="526190" />
              </div>
              <Input label="Месяц начала учёта в системе" value={data.accounting_start_month} onChange={e => setD('accounting_start_month', e.target.value)} placeholder="Декабрь 2025" />
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <Input label="Токен бота (из @BotFather)" type="password" value={data.tg_bot_token} onChange={e => setD('tg_bot_token', e.target.value)} placeholder="1234567890:AAF..." />
              <div className="grid grid-cols-2 gap-3">
                <Input label="ID канала для отчётов" value={data.tg_channel_id} onChange={e => setD('tg_channel_id', e.target.value)} placeholder="-100123456789" />
                <Input label="Ваш Telegram ID" value={data.tg_admin_id} onChange={e => setD('tg_admin_id', e.target.value)} placeholder="123456789" />
              </div>
              <div className="p-3 bg-gray-50 rounded-xl text-xs text-gray-500">
                Бот должен быть администратором канала чтобы отправлять отчёты. Можно пропустить и настроить позже в Настройках.
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-8 py-5 border-t border-gray-100 bg-gray-50 flex justify-between items-center">
          <span className="text-xs text-gray-400">Шаг {step + 1} из {STEPS.length}</span>
          <div className="flex gap-2">
            {step > 0 && <Button variant="ghost" onClick={() => setStep(s => s - 1)}>Назад</Button>}
            {step < STEPS.length - 1 ? (
              <Button variant="primary" onClick={() => setStep(s => s + 1)}>Далее →</Button>
            ) : (
              <Button variant="primary" onClick={handleFinish} loading={saving}>
                <Check size={14} /> Завершить настройку
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
