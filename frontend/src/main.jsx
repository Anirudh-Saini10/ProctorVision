import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { SessionProvider } from './state/SessionContext.jsx'
import { WebSocketProvider } from './state/WebSocketContext.jsx'
import { AuthProvider } from './state/AuthContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <SessionProvider>
          <WebSocketProvider>
            <App />
          </WebSocketProvider>
        </SessionProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
