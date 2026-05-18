import { useNavigate } from '@tanstack/react-router'
import { SearchBox } from '@/components/query/SearchBox'
import { SuggestedTopics } from '@/components/query/SuggestedTopics'

export default function Home() {
  const navigate = useNavigate()

  const handleQuery = (query: string) => {
    navigate({ to: '/query', search: { q: query, qid: undefined, fresh: false } })
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-8 px-4">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Godspeed</h1>
        <p className="mt-2 text-sm text-stone-500">Ask anything about your engineering knowledge base.</p>
      </div>
      <SearchBox onSubmit={handleQuery} className="w-full" />
      <SuggestedTopics onSelect={handleQuery} />
    </div>
  )
}
