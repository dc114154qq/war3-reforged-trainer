import { Component, type ErrorInfo, type ReactNode, useEffect } from 'react'

declare global {
  interface Window {
    __war3Startup?: { ready(): void; fail(message: string, stack?: string): void }
  }
}

/** Lives inside the page Suspense boundary: a shell alone is not a loaded page. */
export function FrontendReady() {
  useEffect(() => {
    // A committed page is available even if Windows throttles background animation frames.
    window.__war3Startup?.ready()
  }, [])
  return null
}

export class FrontendBoundary extends Component<{ children: ReactNode }, { error: string }> {
  state = { error: '' }

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : String(error) }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    window.__war3Startup?.fail(error.message, `${error.stack ?? ''}\n${info.componentStack ?? ''}`)
  }

  render() {
    if (this.state.error) return <div role="alert" style={{ padding: 32, color: '#eee', background: '#121a2b', whiteSpace: 'pre-wrap' }}>
      界面加载失败 / Interface failed to load{ '\n' }{this.state.error}
    </div>
    return this.props.children
  }
}
