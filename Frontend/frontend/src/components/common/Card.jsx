export function Card({ as: Element = 'div', className = '', children, ...props }) {
  return <Element className={`card${className ? ` ${className}` : ''}`} {...props}>{children}</Element>
}
