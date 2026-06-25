import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props   { children: ReactNode }
interface State   { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  override render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
          <p className="text-lg font-semibold text-stone-800 dark:text-stone-200">
            Something went wrong
          </p>
          <p className="max-w-md text-sm text-stone-500">
            {this.state.error.message}
          </p>
          <div className="flex gap-3">
            <button
              className="rounded bg-brand px-4 py-2 text-sm text-white hover:bg-brand-dark"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
            <a
              href="/"
              className="rounded border border-stone-300 bg-white px-4 py-2 text-sm text-stone-700 hover:bg-stone-50 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-200"
            >
              Go home
            </a>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
