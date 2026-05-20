import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

function App(): JSX.Element {
  return <div>CBIM v2 — UI skeleton</div>
}

const root = document.getElementById('root')
if (root === null) {
  throw new Error('Root element not found')
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>
)
