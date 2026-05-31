import { useState, useCallback } from 'react'
import { searchRestaurants } from '../api/client'

export function useSearch() {
  const [results, setResults] = useState([])
  const [meta, setMeta] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const search = useCallback(async (address, travelMode) => {
    if (!address.trim()) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await searchRestaurants(address, travelMode)
      setResults(data.results || [])
      setMeta(data.meta || null)
    } catch (err) {
      setError(err.message)
      setResults([])
      setMeta(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { results, meta, isLoading, error, search }
}
