import { create } from 'zustand'

type DateRange = '7d' | '30d' | '90d'

interface FilterState {
  dateRange:   DateRange
  teamFilter:  string | null
  sourceFilter: string | null
  setDateRange:    (r: DateRange) => void
  setTeamFilter:   (t: string | null) => void
  setSourceFilter: (s: string | null) => void
  reset: () => void
}

const defaults = { dateRange: '30d' as DateRange, teamFilter: null, sourceFilter: null }

export const useFilterStore = create<FilterState>()((set) => ({
  ...defaults,
  setDateRange:    (dateRange)    => set({ dateRange }),
  setTeamFilter:   (teamFilter)   => set({ teamFilter }),
  setSourceFilter: (sourceFilter) => set({ sourceFilter }),
  reset: () => set(defaults),
}))
