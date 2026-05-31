import TravelModeToggle from '../search/TravelModeToggle'
import AddressInput from '../search/AddressInput'
import PriceSlider from '../filters/PriceSlider'
import CuisinePills from '../filters/CuisinePills'
import SortDropdown from '../filters/SortDropdown'
import './StickyFilterBar.css'

export default function StickyFilterBar({
  address,
  setAddress,
  travelMode,
  setTravelMode,
  priceMax,
  setPriceMax,
  selectedCuisines,
  toggleCuisine,
  sortBy,
  setSortBy,
  onSearch,
  isLoading,
}) {
  return (
    <div className="filter-bar">
      <div className="filter-bar-inner">
        <div className="filter-bar-top">
          <AddressInput
            address={address}
            setAddress={setAddress}
            onSearch={onSearch}
            isLoading={isLoading}
          />
          <TravelModeToggle mode={travelMode} setMode={setTravelMode} />
        </div>

        <div className="filter-bar-controls">
          <PriceSlider value={priceMax} onChange={setPriceMax} />
          <SortDropdown value={sortBy} onChange={setSortBy} />
        </div>

        <CuisinePills
          selected={selectedCuisines}
          onToggle={toggleCuisine}
        />
      </div>
    </div>
  )
}
