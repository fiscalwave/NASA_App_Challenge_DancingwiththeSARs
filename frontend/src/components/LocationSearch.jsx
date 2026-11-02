import { useState } from 'react'
import { SearchIcon } from 'lucide-react'

export default function LocationSearch({ onSearch }) {
  const [location, setLocation] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (location) {
      onSearch(location)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative">
        <SearchIcon className="absolute left-3 top-3 w-5 h-5 text-text-secondary" />
        <input
          type="text"
          placeholder="Search location..."
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg text-text-primary placeholder-text-secondary focus:outline-none focus:border-blue-500"
        />
      </div>
    </form>
  )
}
