import { TRAVEL_MODES } from '../../utils/constants'
import './ResultsHeader.css'

export default function ResultsHeader({ meta, priceMax, resultCount }) {
  const modeLabel = TRAVEL_MODES.find((m) => m.key === meta.travel_mode)
  const timeWindow = meta.radius_expanded ? '45' : '20'

  return (
    <div className="results-header">
      <p className="results-header-text">
        <span className="results-header-count">{resultCount}</span>
        {resultCount === 1 ? ' spot' : ' spots'} under ${priceMax} within {timeWindow} min{' '}
        {modeLabel?.icon} {modeLabel?.label.toLowerCase()}
      </p>
      {meta.radius_expanded && (
        <span className="results-header-badge">Expanded radius</span>
      )}
    </div>
  )
}
