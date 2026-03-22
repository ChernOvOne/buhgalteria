import { useState } from 'react'
import { reportsAPI } from '@/api'
import { downloadBlob, today, monthStart, yearStart } from '@/utils'
import { Button, Input } from '@/components/ui'
import { PageHeader } from '@/components/layout'
import { FileDown, FileText, Table2 } from 'lucide-react'
import toast from 'react-hot-toast'

const PRESETS = [
  { label: 'Сегодня',         from: today,      to: today },
  { label: 'Этот месяц',      from: monthStart,  to: today },
  { label: 'Этот год',        from: yearStart,   to: today },
]

export default function ReportsPage() {
  const [dateFrom, setDateFrom] = useState(monthStart())
  const [dateTo, setDateTo] = useState(today())
  const [loading, setLoading] = useState(null)

  const handleExport = async (format) => {
    setLoading(format)
    try {
      const fn = format === 'pdf' ? reportsAPI.pdf : reportsAPI.excel
      const res = await fn({ date_from: dateFrom, date_to: dateTo, format })
      const ext = format === 'pdf' ? 'pdf' : 'xlsx'
      downloadBlob(res.data, `report_${dateFrom}_${dateTo}.${ext}`)
      toast.success('Отчёт скачан')
    } catch { toast.error('Ошибка генерации отчёта') }
    finally { setLoading(null) }
  }

  const handleQuick = async (period, format) => {
    setLoading(`${period}-${format}`)
    try {
      const res = await reportsAPI.quick(period, format)
      const ext = format === 'pdf' ? 'pdf' : 'xlsx'
      downloadBlob(res.data, `report_${period}.${ext}`)
      toast.success('Отчёт скачан')
    } catch { toast.error('Ошибка') }
    finally { setLoading(null) }
  }

  return (
    <div>
      <PageHeader title="Отчёты" subtitle="Экспорт финансовых данных" />

      <div className="p-3 md:p-5 space-y-4">

        {/* Custom period */}
        <div className="bg-white border border-gray-100 rounded-xl p-6">
          <div className="text-sm font-medium mb-4">Произвольный период</div>
          <div className="flex gap-3 items-end flex-wrap">
            <Input label="С" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-40" />
            <Input label="По" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-40" />
            <Button variant="danger" onClick={() => handleExport('pdf')} loading={loading === 'pdf'}>
              <FileText size={14} /> Скачать PDF
            </Button>
            <Button variant="success" onClick={() => handleExport('excel')} loading={loading === 'excel'}>
              <Table2 size={14} /> Скачать Excel
            </Button>
          </div>
        </div>

        {/* Quick exports */}
        <div className="bg-white border border-gray-100 rounded-xl p-6">
          <div className="text-sm font-medium mb-4">Быстрый экспорт</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {PRESETS.map(({ label, from, to }) => (
              <div key={label} className="border border-gray-100 rounded-xl p-4">
                <div className="text-sm font-medium mb-1">{label}</div>
                <div className="text-xs text-gray-400 mb-3">{from()} — {to()}</div>
                <div className="flex gap-2">
                  <Button size="sm" variant="danger" onClick={() => handleQuick(
                    label === 'Сегодня' ? 'today' : label === 'Этот месяц' ? 'month' : 'year', 'pdf'
                  )} loading={loading === `${label}-pdf`}>
                    <FileText size={12} /> PDF
                  </Button>
                  <Button size="sm" variant="success" onClick={() => handleQuick(
                    label === 'Сегодня' ? 'today' : label === 'Этот месяц' ? 'month' : 'year', 'excel'
                  )} loading={loading === `${label}-excel`}>
                    <Table2 size={12} /> Excel
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* What's included */}
        <div className="bg-gray-50 border border-gray-100 rounded-xl p-5">
          <div className="text-sm font-medium mb-3">Что входит в отчёт</div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-sm text-gray-600">
            {[
              'KPI за период (доход, расход, прибыль)',
              'Расходы по категориям с процентами',
              'Детализация всех транзакций',
              'Сводка по партнёрам и выплатам',
              'История инкассации (ДВД, возвраты)',
              'Рекламные кампании с ROI',
              'Логотип и дата формирования',
              'Готов к печати и отправке инвесторам',
            ].map(item => (
              <div key={item} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-primary-400 flex-shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
