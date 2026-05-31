import './AddressInput.css'

export default function AddressInput({ address, setAddress, onSearch, isLoading }) {
  return (
    <form className="address-input" onSubmit={onSearch}>
      <span className="address-input-icon">📍</span>
      <input
        type="text"
        className="address-input-field"
        placeholder="Enter your address..."
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        aria-label="Street address"
      />
      <button
        type="submit"
        className="address-input-btn"
        disabled={isLoading || !address.trim()}
      >
        {isLoading ? 'Searching...' : 'Find Food'}
      </button>
    </form>
  )
}
