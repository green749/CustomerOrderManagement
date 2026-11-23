export function Input({ label, error, id, className = '', bare = false, ...props }) {
  const inputId = id ?? props.name
  const input = <input id={inputId} className={className} aria-invalid={Boolean(error)} aria-describedby={error ? `${inputId}-error` : undefined} {...props} />
  if (bare) return input
  return (
    <label className={`field-control${error ? ' field-control-invalid' : ''}`}>
      {label && <span>{label}</span>}
      {input}
      {error && <small id={`${inputId}-error`}>{error}</small>}
    </label>
  )
}
