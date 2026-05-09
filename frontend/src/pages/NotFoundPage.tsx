import { Link } from '@tanstack/react-router'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <p className="text-5xl font-bold text-stone-300">404</p>
      <p className="text-stone-500">Page not found</p>
      <Link to="/" className="text-sm text-brand underline">
        Back to home
      </Link>
    </div>
  )
}
