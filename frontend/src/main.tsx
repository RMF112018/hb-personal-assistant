import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Providers } from './app/providers'
import { AppRouter } from './app/routes'
import { ErrorBoundary } from './components/ui/ErrorBoundary'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <ErrorBoundary>
        <AppRouter />
      </ErrorBoundary>
    </Providers>
  </StrictMode>,
)
