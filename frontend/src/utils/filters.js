export function filterByPrice(results, maxPrice) {
  return results.filter((r) => {
    const priceMap = { '$': 7, '$$': 12, '$$$': 20, '$$$$': 30 }
    const estimated = priceMap[r.price_level] || 10
    return estimated <= maxPrice
  })
}

export function filterByCuisine(results, selectedCuisines) {
  if (!selectedCuisines.length || selectedCuisines.includes('all')) {
    return results
  }
  return results.filter((r) =>
    r.cuisine_tags.some((tag) =>
      selectedCuisines.some(
        (sel) => tag.toLowerCase().includes(sel.toLowerCase())
      )
    )
  )
}

export function sortResults(results, sortBy) {
  const sorted = [...results]
  switch (sortBy) {
    case 'rated':
      return sorted.sort((a, b) => b.score - a.score)
    case 'cheapest':
      return sorted.sort((a, b) => {
        const priceMap = { '$': 1, '$$': 2, '$$$': 3, '$$$$': 4 }
        return (priceMap[a.price_level] || 2) - (priceMap[b.price_level] || 2)
      })
    case 'closest':
      return sorted.sort((a, b) => a.travel_time_minutes - b.travel_time_minutes)
    case 'reviewed':
      return sorted.sort((a, b) => b.review_count - a.review_count)
    default:
      return sorted
  }
}
