import { TRAVEL_MODES } from '../../utils/constants'
import './TravelModeToggle.css'

export default function TravelModeToggle({ mode, setMode }) {
  return (
    <div className="travel-toggle" role="radiogroup" aria-label="Travel mode">
      {TRAVEL_MODES.map((m) => (
        <button
          key={m.key}
          className={`travel-toggle-btn ${mode === m.key ? 'active' : ''}`}
          onClick={() => setMode(m.key)}
          role="radio"
          aria-checked={mode === m.key}
          aria-label={m.label}
        >
          <span className="travel-toggle-icon">{m.icon}</span>
          <span className="travel-toggle-label">{m.label}</span>
        </button>
      ))}
    </div>
  )
}
