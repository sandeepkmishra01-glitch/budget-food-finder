import { SORT_OPTIONS } from '../../utils/constants'
import './SortDropdown.css'

export default function SortDropdown({ value, onChange }) {
  return (
    <div className="sort-dropdown">
      <label className="sort-dropdown-label" htmlFor="sort-select">
        Sort by
      </label>
      <select
        id="sort-select"
        className="sort-dropdown-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.key} value={opt.key}>
            {opt.icon} {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
