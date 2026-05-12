export type Role = 'engineer' | 'manager' | 'admin'

export interface Team {
  id:   string
  name: string
}

export interface User {
  id:                  string
  email:               string
  name:                string
  role:                Role
  team_id:             string
  team?:               Team
  is_new_hire:         boolean
  mentor_id?:          string
  allowed_channel_ids?: string[]
}
