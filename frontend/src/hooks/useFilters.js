import { useState, useMemo } from 'react'
import { DEFAULT_PRICE } from '../utils/constants'
import { filterByPrice, filterByCuisine, sortResults } from '../utils/filters'

export function useFilters(results) {
  const [priceMax, setPriceMax] = useState(DEFAULT_PRICE)
  const [selectedCuisines, setSelectedCuisines] = useState([])
  const [sortBy, setSortBy] = useState('rated')

  const filteredResults = useMemo(() => {
    let filtered = filterByPrice(results, priceMax)
    filtered = filterByCuisine(filtered, selectedCuisines)
    filtered = sortResults(filtered, sortBy)
    return filtered
  }, [results, priceMax, selectedCuisines, sortBy])

  const toggleCuisine = (cuisine) => {
    setSelectedCuisines((prev) => {
      if (cuisine === 'all') return []
      if (prev.includes(cuisine)) {
        return prev.filter((c) => c !== cuisine)
      }
      return [...prev, cuisine]
    })
  }

  return {
    priceMax,
    setPriceMax,
    selectedCuisines,
    toggleCuisine,
    sortBy,
    setSortBy,
    filteredResults,
  }
}
