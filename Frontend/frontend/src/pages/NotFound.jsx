import { ArrowLeft, CircleHelp } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <main className="not-found-page">
      <span className="not-found-icon"><CircleHelp size={24} /></span>
      <span className="eyebrow">404 · PAGE NOT FOUND</span>
      <h1>This page is out of the picture.</h1>
      <p>The address may have changed, or the page may no longer be available.</p>
      <Link className="button button-primary" to="/"><ArrowLeft size={16} /> Back to overview</Link>
    </main>
  )
}
