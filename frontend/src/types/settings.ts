/**
 * Settings & Admin Types
 */

// API Keys
export type ApiKeyProvider = 'github' | 'openai' | 'claude' | 'custom'

export interface ApiKey {
  id: string
  provider: ApiKeyProvider
  name: string
  last_used_at?: string
  created_at: string
  is_active: boolean
}

export interface CreateApiKeyInput {
  provider: ApiKeyProvider
  name: string
  secret: string
}

// Audit Log
export type AuditAction =
  | 'grant_channel'
  | 'revoke_channel'
  | 'change_role'
  | 'invite_user'
  | 'deactivate_user'
  | 'query_executed'
  | 'document_accessed'
  | 'bulk_user_import'

export interface AuditLogEntry {
  id: string
  actor_id: string
  actor_name?: string
  actor_email?: string
  action: AuditAction
  target_type: 'user' | 'channel' | 'team' | 'query' | 'document'
  target_id: string
  target_name?: string
  metadata: Record<string, unknown>
  created_at: string
}

// User Management
export interface UserInvite {
  email: string
  name: string
  role: 'engineer' | 'manager' | 'admin' | 'org_admin'
  team_id?: string
  channel_ids?: string[]
}

export interface BulkUserImport {
  users: UserInvite[]
  send_invitations: boolean
}

// Workspace
export interface WorkspaceSettings {
  name: string
  slug: string
  description?: string
  logo_url?: string
  max_team_members?: number
  max_channels?: number
}

// Channel
export type ChannelSensitivity = 'public' | 'internal' | 'confidential' | 'restricted'

export interface Channel {
  id: string
  name: string
  source_type?: string
  sensitivity: ChannelSensitivity
  team_id?: string
  created_at: string
}

export interface CreateChannelInput {
  name: string
  team_id?: string
  source_type?: string
  sensitivity: ChannelSensitivity
}
