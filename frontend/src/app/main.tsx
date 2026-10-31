import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../ds/index.css'
import { DsProvider } from '../ds'
import { App } from './App'

async function boot() {
  // ?mock gives a fake bridge for development and screenshots. pywebview never opens the
  // page with that parameter, and the mock is a separate chunk the app never loads otherwise.
  if (new URLSearchParams(location.search).has('mock') && !window.pywebview) await import('./dev/mockBridge')
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <DsProvider>
        <App />
      </DsProvider>
    </StrictMode>,
  )
}

void boot()
