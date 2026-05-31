import { useState, useEffect } from 'react'
import { fetchCuisines } from '../../api/client'
import './CuisinePills.css'

export default function CuisinePills({ selected, onToggle }) {
  const [cuisines, setCuisines] = useState([
    { key: 'all', label: 'All', emoji: '🍱' },
    { key: 'mexican', label: 'Mexican', emoji: '🌮' },
    { key: 'pizza', label: 'Pizza', emoji: '🍕' },
    { key: 'burgers', label: 'Burgers', emoji: '🍔' },
    { key: 'asian', label: 'Asian', emoji: '🍜' },
    { key: 'healthy', label: 'Healthy', emoji: '🥗' },
    { key: 'chicken', label: 'Chicken', emoji: '🍗' },
    { key: 'wraps', label: 'Wraps', emoji: '🌯' },
    { key: 'sandwiches', label: 'Sandwiches', emoji: '🥪' },
    { key: 'sushi', label: 'Sushi', emoji: '🍣' },
    { key: 'indian', label: 'Indian', emoji: '🍛' },
    { key: 'mediterranean', label: 'Mediterranean', emoji: '🥙' },
    { key: 'italian', label: 'Italian', emoji: '🍝' },
    { key: 'cafe', label: 'Café/Bakery', emoji: '☕' },
    { key: 'bbq', label: 'BBQ', emoji: '🌶️' },
  ])

  useEffect(() => {
    fetchCuisines()
      .then(setCuisines)
      .catch(() => {})
  }, [])

  const isAllSelected = selected.length === 0 || selected.includes('all')

  return (
    <div className="cuisine-pills" role="group" aria-label="Cuisine filter">
      <div className="cuisine-pills-scroll">
        {cuisines.map((c) => {
          const isActive = c.key === 'all' ? isAllSelected : selected.includes(c.key)
          return (
            <button
              key={c.key}
              className={`cuisine-pill ${isActive ? 'active' : ''}`}
              onClick={() => onToggle(c.key)}
              aria-pressed={isActive}
            >
              <span className="cuisine-pill-emoji">{c.emoji}</span>
              <span className="cuisine-pill-label">{c.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
