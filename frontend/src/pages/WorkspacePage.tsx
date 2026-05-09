import { useNavigate } from '@tanstack/react-router'
import { QueryHistory } from '@/components/workspace/QueryHistory'

export default function WorkspacePage() {
  const navigate = useNavigate()

  const handleReplay = (query: string) => {
    navigate({ to: '/query', search: { q: query } })
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Workspace</h1>
      <QueryHistory onReplay={handleReplay} />
    </div>
  )
}
