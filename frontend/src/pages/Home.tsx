import { useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { SearchBox } from '@/components/query/SearchBox'
import { SuggestedTopics } from '@/components/query/SuggestedTopics'
import { WelcomeBanner, shouldShowWelcome } from '@/components/common/WelcomeBanner'

export default function Home() {
  const navigate = useNavigate()
  const user     = useAuthStore((s) => s.user)

  const handleQuery = (query: string) => {
    navigate({ to: '/query', search: { q: query, qid: undefined, fresh: false } })
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-6 px-4 py-12">
      <div className="w-full text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Godspeed</h1>
        <p className="mt-2 text-sm text-stone-500">Ask anything about your engineering knowledge base.</p>
      </div>

      <SearchBox onSubmit={handleQuery} className="w-full" />

      {user && shouldShowWelcome(user) && (
        <WelcomeBanner user={user} onQuery={handleQuery} />
      )}

      {!(user && shouldShowWelcome(user)) && (
        <SuggestedTopics onSelect={handleQuery} />
      )}
    </div>
  )
}
