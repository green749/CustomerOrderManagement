export function Select({ label, id, className = '', children, ...props }) {
  const selectId = id ?? props.name
  return (
    <label className={`field-control${className ? ` ${className}` : ''}`}>
      {label && <span>{label}</span>}
      <select id={selectId} {...props}>{children}</select>
    </label>
  )
}
