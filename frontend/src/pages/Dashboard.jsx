import { useState } from 'react'
import { AlertCircle, MapPin, Calendar, Activity } from 'lucide-react'
import LeafletMap from '../maps/LeafletMap'
import LocationSearch from '../components/LocationSearch'
import DateRangeSelector from '../components/DateRangeSelector'
import { searchAPI, processAPI } from '../services/api'

export default function Dashboard() {
  const [bounds, setBounds] = useState([41.30, 12.70, 41.35, 12.75])
  const [dateRange, setDateRange] = useState({ start: '2024-10-01', end: '2024-11-01' })
  const [scenes, setScenes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedBefore, setSelectedBefore] = useState(null)
  const [selectedAfter, setSelectedAfter] = useState(null)
  const [analysisResults, setAnalysisResults] = useState(null)

  const handleSearch = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await searchAPI.searchScenes(
        bounds,
        dateRange.start,
        dateRange.end
      )
      setScenes(data.scenes)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!selectedBefore || !selectedAfter) {
      setError('Please select both before and after scenes')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const results = await processAPI.analyzeFloodChange(
        selectedBefore.path || selectedBefore.url,
        selectedAfter.path || selectedAfter.url,
        bounds,
        'VVVV',
        {
          floodChange: -2.0,
          lowBackscatter: -15.0,
        }
      )
      setAnalysisResults(results)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex-1 flex">
      {/* Sidebar */}
      <div className="w-96 bg-surface border-r border-border overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Location Section */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <MapPin className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold">Location</h2>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-text-secondary">Bounds (Degrees)</label>
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                  <input
                    type="number"
                    step="0.01"
                    value={bounds[0]}
                    onChange={(e) => setBounds([...bounds.slice(0, 0), parseFloat(e.target.value), ...bounds.slice(1)])}
                    placeholder="West"
                    className="px-2 py-1 bg-background border border-border rounded"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={bounds[1]}
                    onChange={(e) => setBounds([bounds[0], parseFloat(e.target.value), ...bounds.slice(2)])}
                    placeholder="South"
                    className="px-2 py-1 bg-background border border-border rounded"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={bounds[2]}
                    onChange={(e) => setBounds([bounds[0], bounds[1], parseFloat(e.target.value), bounds[3]])}
                    placeholder="East"
                    className="px-2 py-1 bg-background border border-border rounded"
                  />
                  <input
                    type="number"
                    step="0.01"
                    value={bounds[3]}
                    onChange={(e) => setBounds([...bounds.slice(0, 3), parseFloat(e.target.value)])}
                    placeholder="North"
                    className="px-2 py-1 bg-background border border-border rounded"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Date Section */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-5 h-5 text-green-500" />
              <h2 className="text-lg font-semibold">Timeline</h2>
            </div>
            <DateRangeSelector onDateChange={setDateRange} />
          </div>

          {/* Search Button */}
          <button
            onClick={handleSearch}
            disabled={loading}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium rounded-lg transition"
          >
            {loading ? 'Searching...' : 'Search Available Scenes'}
          </button>

          {/* Available Scenes */}
          {scenes.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2">Available Scenes ({scenes.length})</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {scenes.map((scene, idx) => (
                  <div key={idx} className="bg-background p-2 rounded border border-border text-xs cursor-pointer hover:border-blue-500"
                    onClick={() => {
                      if (!selectedBefore) setSelectedBefore(scene)
                      else if (!selectedAfter) setSelectedAfter(scene)
                    }}>
                    <div className="font-mono">{scene.name}</div>
                    <div className="text-text-secondary">{scene.timestamp}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Selected Scenes */}
          {(selectedBefore || selectedAfter) && (
            <div>
              <h3 className="text-sm font-semibold mb-2">Selected Scenes</h3>
              <div className="space-y-2 text-xs">
                {selectedBefore && (
                  <div className="bg-green-900 bg-opacity-20 p-2 rounded">
                    <div className="text-green-400">Before: {selectedBefore.name}</div>
                  </div>
                )}
                {selectedAfter && (
                  <div className="bg-red-900 bg-opacity-20 p-2 rounded">
                    <div className="text-red-400">After: {selectedAfter.name}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Analyze Button */}
          {selectedBefore && selectedAfter && (
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="w-full py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white font-medium rounded-lg transition"
            >
              {loading ? 'Analyzing...' : 'Analyze Change'}
            </button>
          )}

          {/* Analysis Results */}
          {analysisResults && (
            <div className="bg-background border border-border rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-yellow-500" />
                <h3 className="text-sm font-semibold">Analysis Results</h3>
              </div>
              <div className="space-y-2 text-xs text-text-secondary">
                <div>
                  <span className="text-text-primary font-medium">
                    {analysisResults.results.classification_statistics.possible_flood_area_km2.toFixed(2)} km²
                  </span>
                  <span> potential new inundation</span>
                </div>
                <div>
                  <span className="text-text-primary font-medium">
                    {analysisResults.results.classification_statistics.persistent_low_backscatter_area_km2.toFixed(2)} km²
                  </span>
                  <span> persistent water</span>
                </div>
              </div>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <div className="bg-red-900 bg-opacity-20 border border-red-600 p-3 rounded text-sm text-red-400 flex gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Area */}
      <div className="flex-1">
        <LeafletMap bounds={bounds} onBoundsChange={setBounds} />
      </div>
    </div>
  )
}
