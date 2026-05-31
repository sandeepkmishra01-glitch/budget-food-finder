import './EmptyState.css'

const MESSAGES = {
  'no-results': {
    icon: '🗺️',
    title: 'No food spots found',
    text: 'No food spots found in this area. Try a different address.',
  },
  'no-cuisine': {
    icon: '🍽️',
    title: 'No matches for that cuisine',
    text: 'No spots found for your cuisine selection — try another cuisine or expand travel time.',
  },
  'no-price': {
    icon: '💰',
    title: 'Nothing at that price',
    text: null,
  },
  transit: {
    icon: '🚌',
    title: 'Transit unavailable',
    text: 'Transit info not available for this area. Try Drive or Walk.',
  },
  error: {
    icon: '⚠️',
    title: 'Something went wrong',
    text: null,
  },
}

export default function EmptyState({ type, message, priceMax }) {
  const config = MESSAGES[type] || MESSAGES['no-results']

  let displayText = config.text || message
  if (type === 'no-price') {
    displayText = `No dishes under $${priceMax} nearby — try $${priceMax + 3} or higher.`
  }

  return (
    <div className="empty-state">
      <span className="empty-state-icon">{config.icon}</span>
      <h3 className="empty-state-title">{config.title}</h3>
      <p className="empty-state-text">{displayText}</p>
    </div>
  )
}
