import { PRICE_STEPS } from '../../utils/constants'
import './PriceSlider.css'

export default function PriceSlider({ value, onChange }) {
  const currentIndex = PRICE_STEPS.indexOf(value)

  return (
    <div className="price-slider">
      <label className="price-slider-label">
        Showing dishes under <strong>${value}</strong>
      </label>
      <div className="price-slider-track">
        {PRICE_STEPS.map((step, i) => (
          <button
            key={step}
            className={`price-slider-step ${i <= currentIndex ? 'active' : ''} ${step === value ? 'current' : ''}`}
            onClick={() => onChange(step)}
            aria-label={`Under $${step}`}
          >
            <span className="price-slider-dot" />
            <span className="price-slider-value">${step}</span>
          </button>
        ))}
        <div
          className="price-slider-fill"
          style={{ width: `${(currentIndex / (PRICE_STEPS.length - 1)) * 100}%` }}
        />
      </div>
    </div>
  )
}
