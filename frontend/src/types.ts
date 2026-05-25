// Shared types matching the FastAPI schemas in backend/app/schemas/.
// Keep these in sync if you change the backend.

export type DocumentStatus = 'pending' | 'processing' | 'indexed' | 'failed'

export interface Document {
  id: string
  filename: string
  status: DocumentStatus
  chunk_count: number
  file_size: number
  mime_type: string
  error: string | null
  created_at: string
  indexed_at: string | null
}

export interface DocumentList {
  items: Document[]
  total: number
}

export interface Citation {
  short_id: string
  chunk_id: string
  document_id: string
  document_filename: string
  page: number
  snippet: string
  score: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  isStreaming?: boolean
  error?: string | null
}

export interface HealthResponse {
  status: string
  version: string
  environment: string
}
