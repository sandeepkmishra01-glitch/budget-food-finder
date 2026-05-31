import ResultCard from './ResultCard'
import './ResultsGrid.css'

export default function ResultsGrid({ results }) {
  return (
    <div className="results-grid">
      {results.map((result) => (
        <ResultCard key={result.id} result={result} />
      ))}
    </div>
  )
}
