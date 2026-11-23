import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import './theme.css'
import './index.css'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds fresh cache
      gcTime: 5 * 60 * 1000, // 5 minutes in memory
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

document.documentElement.dataset.theme = localStorage.getItem('theme') || 'dark'
if (!localStorage.getItem('theme')) {
  localStorage.setItem('theme', 'dark')
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </QueryClientProvider>,
)
