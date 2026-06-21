import React from 'react'

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg, #0a0a14)',
          zIndex: 99999,
        }}>
          <div style={{
            maxWidth: 480,
            width: '90%',
            padding: '32px 28px',
            borderRadius: 'var(--radius, 12px)',
            background: 'var(--glass-bg, rgba(20, 20, 35, 0.9))',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            boxShadow: '0 16px 48px rgba(0, 0, 0, 0.5), 0 0 1px rgba(255, 255, 255, 0.06)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: 40,
              marginBottom: 16,
            }}>⚠️</div>
            <h2 style={{
              margin: '0 0 12px',
              fontSize: 18,
              fontWeight: 600,
              color: '#ef4444',
              letterSpacing: '-0.01em',
            }}>Component Error</h2>
            <p style={{
              margin: '0 0 20px',
              fontSize: 13,
              lineHeight: 1.6,
              color: 'var(--text-secondary, #9ca3af)',
              wordBreak: 'break-word',
            }}>
              {this.state.error?.message || 'Unknown error'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                padding: '10px 24px',
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 'var(--radius, 8px)',
                color: '#ef4444',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                (e.target as HTMLElement).style.background = 'rgba(239, 68, 68, 0.25)'
              }}
              onMouseLeave={e => {
                (e.target as HTMLElement).style.background = 'rgba(239, 68, 68, 0.15)'
              }}
            >
              Попробовать снова
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
