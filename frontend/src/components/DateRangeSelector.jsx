import { useState } from 'react'
import { Calendar } from 'lucide-react'

export default function DateRangeSelector({ onDateChange }) {
  const [startDate, setStartDate] = useState('2024-10-01')
  const [endDate, setEndDate] = useState('2024-11-01')

  const handleStartChange = (e) => {
    const newStart = e.target.value
    setStartDate(newStart)
    onDateChange({ start: newStart, end: endDate })
  }

  const handleEndChange = (e) => {
    const newEnd = e.target.value
    setEndDate(newEnd)
    onDateChange({ start: startDate, end: newEnd })
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="text-sm font-medium text-text-secondary">Start Date</label>
        <div className="relative mt-1">
          <Calendar className="absolute left-3 top-3 w-4 h-4 text-text-secondary" />
          <input
            type="date"
            value={startDate}
            onChange={handleStartChange}
            className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>
      <div>
        <label className="text-sm font-medium text-text-secondary">End Date</label>
        <div className="relative mt-1">
          <Calendar className="absolute left-3 top-3 w-4 h-4 text-text-secondary" />
          <input
            type="date"
            value={endDate}
            onChange={handleEndChange}
            className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>
    </div>
  )
}
