import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../ds/index.css'
import { DsProvider } from '../ds'
import { StyleGuide } from './StyleGuide'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DsProvider>
      <StyleGuide />
    </DsProvider>
  </StrictMode>,
)
