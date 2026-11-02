import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const searchAPI = {
  searchScenes: async (bounds, startDate, endDate, username = null, password = null) => {
    const response = await api.post('/search/scenes', {
      bounds: {
        west: bounds[0],
        south: bounds[1],
        east: bounds[2],
        north: bounds[3],
      },
      start_date: startDate,
      end_date: endDate,
      username,
      password,
    })
    return response.data
  },

  getPolarizations: async (scenePath) => {
    const response = await api.get('/search/polarizations', {
      params: { scene_path: scenePath },
    })
    return response.data
  },
}

export const processAPI = {
  analyzeFloodChange: async (beforeScene, afterScene, bounds, polarization, thresholds) => {
    const response = await api.post('/process/analyze', {
      before_scene: beforeScene,
      after_scene: afterScene,
      bounds: {
        west: bounds[0],
        south: bounds[1],
        east: bounds[2],
        north: bounds[3],
      },
      polarization,
      flood_change_threshold_db: thresholds.floodChange,
      low_backscatter_threshold_db: thresholds.lowBackscatter,
    })
    return response.data
  },
}

export const exportAPI = {
  downloadGeoTIFF: async (fileType) => {
    const response = await api.get(`/export/geotiff/${fileType}`, {
      responseType: 'blob',
    })
    return response.data
  },

  downloadGeoJSON: async (layerType) => {
    const response = await api.get(`/export/geojson/${layerType}`)
    return response.data
  },
}

export default api
