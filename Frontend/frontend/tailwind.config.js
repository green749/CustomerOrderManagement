/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--text-primary)',
        violet: 'var(--brand-purple)',
        lavender: 'var(--brand-purple-soft)',
        page: 'var(--page-bg)',
        surface: 'var(--surface-hi)',
        muted: 'var(--text-secondary)',
        brand: {
          purple: 'var(--brand-purple)',
          blue: 'var(--brand-blue)',
          orange: 'var(--brand-orange)',
          navy: 'var(--brand-navy)',
        },
      },
    },
  },
  plugins: [],
}
