import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 2 min pour les gros fichiers
})

// Injecter le JWT automatiquement
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirection vers /login si 401 (sauf si on y est déjà ou si c'est une tentative de login)
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isLoginPath = window.location.pathname === '/login'
    if (err.response?.status === 401 && !isLoginPath) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ─── Types ──────────────────────────────────────────────────────────────────

export interface User {
  id: number
  username: string
  email: string
  created_at: string
}

export interface Document {
  id: number
  filename: string
  original_name: string
  file_type: string
  language?: string
  doc_type?: string
  subject?: string
  title_suggested?: string
  confidence?: number
  minio_raw_path?: string
  num_chunks: number
  status: 'pending' | 'processing' | 'ready' | 'error'
  created_at: string
}

export interface ChatSource {
  chunk_text: string
  page?: number
  score: number
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  model_used: string
}

export interface ConversationMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources?: string
  created_at: string
}

export interface ChatSession {
  id: number
  title: string
  document_id?: number
  created_at: string
  updated_at: string
}

export interface DashboardStats {
  total_documents: number
  documents_by_subject: Record<string, number>
  documents_by_type: Record<string, number>
  recent_activity: Document[]
  total_conversations: number
}

export interface Entity {
  text: string
  label: string
}

export interface Subject {
  id: number
  name: string
  color: string | null
  icon: string | null
  is_default: boolean
  created_at: string
}

export interface SubjectCreate {
  name: string
  color?: string
  icon?: string
}

export interface SubjectUpdate {
  name?: string
  color?: string
  icon?: string
  is_default?: boolean
}

// ─── API helpers ─────────────────────────────────────────────────────────────

export const authApi = {
  register: (data: { username: string; email: string; password: string }) =>
    api.post('/auth/register', data),
  login: (data: { username: string; password: string }) =>
    api.post('/auth/login', data),
  me: () => api.get<User>('/auth/me'),
}

export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
      }
    })
  },
  list: (params?: { subject?: string; doc_type?: string }) =>
    api.get<{ documents: Document[]; total: number }>('/documents/', { params }),
  get: (id: number) => api.get<Document>(`/documents/${id}`),
  downloadUrl: (id: number) => api.get<{ url: string }>(`/documents/${id}/download-url`),
  rename: (id: number, new_name: string) => api.patch(`/documents/${id}/rename`, { new_name }),
  delete: (id: number) => api.delete(`/documents/${id}`),
  summary: (id: number) => api.get<{ summary: string }>(`/documents/${id}/summary`),
  entities: (id: number) => api.get<{ entities: Entity[] }>(`/documents/${id}/entities`),
}

export const chatApi = {
  ask: (content: string, document_id?: number, session_id?: number) =>
    api.post<ChatResponse>('/chat/ask', { content, document_id, session_id }),
  history: (session_id?: number, document_id?: number) =>
    api.get<{ messages: ConversationMessage[] }>('/chat/history', {
      params: { ...(session_id && { session_id }), ...(document_id && { document_id }) }
    }),
  clearHistory: (session_id?: number, document_id?: number) =>
    api.delete('/chat/history', { params: { ...(session_id && { session_id }), ...(document_id && { document_id }) } }),
  getSessions: () => api.get<ChatSession[]>('/chat/sessions'),
  createSession: (document_id?: number) => api.post<ChatSession>('/chat/sessions', null, { params: document_id ? { document_id } : {} }),
  deleteSession: (id: number) => api.delete(`/chat/sessions/${id}`),
}

export const dashboardApi = {
  stats: () => api.get<DashboardStats>('/dashboard/stats'),
}

export const subjectsApi = {
  list:   ()                              => api.get<Subject[]>('/subjects/'),
  create: (data: SubjectCreate)           => api.post<Subject>('/subjects/', data),
  update: (id: number, data: SubjectUpdate) => api.patch<Subject>(`/subjects/${id}`, data),
  delete: (id: number)                   => api.delete(`/subjects/${id}`),
  reset:  ()                              => api.post<Subject[]>('/subjects/reset'),
}
