import { MapContainer, TileLayer, Marker, Popup, Rectangle, useMapEvent } from 'react-leaflet'
import L from 'leaflet'

export default function LeafletMap({ bounds, onBoundsChange }) {
  const center = [
    (bounds[1] + bounds[3]) / 2,
    (bounds[0] + bounds[2]) / 2,
  ]

  function MapEvents() {
    const map = useMapEvent('moveend', () => {
      const bounds = map.getBounds()
      onBoundsChange([
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ])
    })
    return null
  }

  return (
    <MapContainer
      center={center}
      zoom={8}
      style={{ width: '100%', height: '100%' }}
      className="rounded-lg"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      <Rectangle bounds={[[bounds[1], bounds[0]], [bounds[3], bounds[2]]]} color="blue" />
      <MapEvents />
    </MapContainer>
  )
}
