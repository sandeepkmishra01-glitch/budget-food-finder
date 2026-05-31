import './ResultCard.css'

export default function ResultCard({ result }) {
  const {
    name,
    address,
    photo_url,
    travel_time_minutes,
    travel_mode,
    rating,
    review_count,
    price_level,
    snippets = [],
    dish_mentions = [],
  } = result

  const modeIcons = { walking: '🚶', transit: '🚌', driving: '🚗' }

  return (
    <article className="result-card">
      <div className="result-card-image">
        {photo_url ? (
          <img src={photo_url} alt={`Food from ${name}`} loading="lazy" />
        ) : (
          <div className="result-card-placeholder">
            <span>🍽️</span>
          </div>
        )}
        <div className="result-card-travel">
          {modeIcons[travel_mode]} {travel_time_minutes} min
        </div>
      </div>

      <div className="result-card-body">
        {dish_mentions.length > 0 && (
          <div className="result-card-dishes">
            {dish_mentions.slice(0, 3).map((dish) => (
              <span key={dish} className="result-card-dish">{dish}</span>
            ))}
          </div>
        )}

        <h3 className="result-card-name">{name}</h3>

        <div className="result-card-meta">
          <span className="result-card-rating">
            ⭐ {rating?.toFixed(1)}
          </span>
          <span className="result-card-reviews">
            ({review_count?.toLocaleString()})
          </span>
          {price_level && (
            <span className="result-card-price">{price_level}</span>
          )}
        </div>

        {snippets.length > 0 && (
          <div className="result-card-snippets">
            {snippets.slice(0, 2).map((snippet, i) => (
              <p key={i} className="result-card-snippet">
                <span className="result-card-snippet-icon">
                  {snippet.source === 'yelp' ? '🟥' : '🟦'}
                </span>
                &ldquo;{snippet.text}&rdquo;
              </p>
            ))}
          </div>
        )}

        <p className="result-card-address">{address}</p>
      </div>
    </article>
  )
}
