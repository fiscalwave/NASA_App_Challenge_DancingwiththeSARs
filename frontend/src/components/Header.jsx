import { Satellite } from 'lucide-react'

export default function Header() {
  return (
    <header className="bg-surface border-b border-border">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Satellite className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">NISAR</h1>
            <p className="text-sm text-text-secondary">Flood & Wetland Monitor</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          <span className="text-sm text-text-secondary">Live</span>
        </div>
      </div>
    </header>
  )
}
