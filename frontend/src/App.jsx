import { useState } from 'react'
import { useSearch } from './hooks/useSearch'
import { useFilters } from './hooks/useFilters'
import './App.css'
import StickyFilterBar from './components/layout/StickyFilterBar'
import ResultsGrid from './components/results/ResultsGrid'
import EmptyState from './components/results/EmptyState'
import ResultsHeader from './components/layout/ResultsHeader'

export default function App() {
  const [address, setAddress] = useState('')
  const [travelMode, setTravelMode] = useState('driving')
  const { results, meta, isLoading, error, search } = useSearch()
  const {
    priceMax,
    setPriceMax,
    selectedCuisines,
    toggleCuisine,
    sortBy,
    setSortBy,
    filteredResults,
  } = useFilters(results)

  const handleSearch = (e) => {
    e?.preventDefault?.()
    search(address, travelMode)
  }

  const handleModeChange = (mode) => {
    setTravelMode(mode)
    if (address.trim()) {
      search(address, mode)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">
          <span className="app-title-accent">Budget</span> Food Finder
        </h1>
        <p className="app-subtitle">Discover the best eats near you, without breaking the bank</p>
      </header>

      <StickyFilterBar
        address={address}
        setAddress={setAddress}
        travelMode={travelMode}
        setTravelMode={handleModeChange}
        priceMax={priceMax}
        setPriceMax={setPriceMax}
        selectedCuisines={selectedCuisines}
        toggleCuisine={toggleCuisine}
        sortBy={sortBy}
        setSortBy={setSortBy}
        onSearch={handleSearch}
        isLoading={isLoading}
      />

      <main className="main-content">
        {meta && (
          <ResultsHeader
            meta={meta}
            priceMax={priceMax}
            resultCount={filteredResults.length}
          />
        )}

        {error && <EmptyState type="error" message={error} />}

        {meta && meta.transit_unavailable && (
          <EmptyState type="transit" />
        )}

        {meta && !meta.transit_unavailable && filteredResults.length === 0 && !isLoading && (
          <EmptyState
            type={
              results.length === 0
                ? 'no-results'
                : selectedCuisines.length > 0
                ? 'no-cuisine'
                : 'no-price'
            }
            priceMax={priceMax}
          />
        )}

        {filteredResults.length > 0 && (
          <ResultsGrid results={filteredResults} />
        )}

        {!meta && !isLoading && !error && (
          <div className="landing-state">
            <p className="landing-prompt">Enter your address above to find great food nearby</p>
          </div>
        )}
      </main>
    </div>
  )
}
