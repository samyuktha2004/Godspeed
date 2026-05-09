import { useState } from 'react'

interface UsePaginationOptions {
  total:     number
  pageSize?: number
}

interface UsePaginationResult {
  page:       number
  pageSize:   number
  totalPages: number
  offset:     number
  canPrev:    boolean
  canNext:    boolean
  goTo:       (p: number) => void
  nextPage:   () => void
  prevPage:   () => void
  reset:      () => void
}

export function usePagination({ total, pageSize = 20 }: UsePaginationOptions): UsePaginationResult {
  const [page, setPage] = useState(1)

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const clamp      = (p: number) => Math.min(Math.max(1, p), totalPages)

  return {
    page,
    pageSize,
    totalPages,
    offset:   (page - 1) * pageSize,
    canPrev:  page > 1,
    canNext:  page < totalPages,
    goTo:     (p)  => setPage(clamp(p)),
    nextPage: ()   => setPage((p) => clamp(p + 1)),
    prevPage: ()   => setPage((p) => clamp(p - 1)),
    reset:    ()   => setPage(1),
  }
}
