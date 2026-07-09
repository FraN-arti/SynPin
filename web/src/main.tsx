import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

// Hide the boot loader injected by index.html. The CSS fade-out
// runs once before this code executes, so we just need to add
// .gone to actually remove the element from the layout (display:none
// short-circuits the animation so we can't keep the fade visually).
const bootLoader = document.getElementById('boot-loader')
if (bootLoader) {
  // Wait one frame so the boot animation has a chance to play
  // before we hide the element. Without this, a fast mount can
  // remove it before the first paint, defeating the purpose.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      bootLoader.classList.add('gone')
    })
  })
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
