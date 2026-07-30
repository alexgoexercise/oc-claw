export interface SessionInfo {
  id: string
  label?: string
  status: string
  model?: string
  channel?: string
}

export interface CharacterMeta {
  name: string
  builtin?: boolean
  ip?: string
  workGifs: string[]
  restGifs: string[]
  crawlGifs?: string[]
  angryGifs?: string[]
  shyGifs?: string[]
  miniActions?: Record<string, string[]>
  largeActions?: Record<string, string>
}

export interface AgentInfo {
  id: string
  identityName?: string
  identityEmoji?: string
}

export interface AgentHealth {
  agentId: string
  active: boolean
}

export interface ToolCallStat {
  name: string
  count: number
}

export interface RecentAction {
  type: 'tool' | 'text'
  summary: string
  detail?: string
  timestamp?: string
}

export interface AgentMetrics {
  agentId: string
  active: boolean
  currentModel?: string
  thinkingLevel?: string
  activeSessionCount: number
  currentTask?: string
  currentTool?: string
  totalTokens: number
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  cacheWriteTokens: number
  totalCost: number
  toolCalls: ToolCallStat[]
  recentActions: RecentAction[]
  errorCount: number
  messageCount: number
  sessionStart?: string
  lastActivity?: string
  channel?: string
}

export interface OcConnection {
  id: string
  type: 'local' | 'remote'
  host?: string
  user?: string
}
