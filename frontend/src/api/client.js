const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function searchRestaurants(address, travelMode) {
  const resp = await fetch(`${API_BASE}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address, travel_mode: travelMode }),
  })
  if (!resp.ok) throw new Error(`Search failed: ${resp.status}`)
  return resp.json()
}

export async function fetchCuisines() {
  const resp = await fetch(`${API_BASE}/api/cuisines`)
  if (!resp.ok) throw new Error(`Failed to fetch cuisines: ${resp.status}`)
  return resp.json()
}
