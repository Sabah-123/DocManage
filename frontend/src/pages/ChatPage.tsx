import { useState, useRef, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Send, Trash2, BookOpen, Loader2, Paperclip, FileText, Copy, Check, MessageSquarePlus } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { chatApi, documentsApi, ConversationMessage, Document, ChatSession } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: { chunk: string; score: number }[]
  streaming?: boolean
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-gray-100 rounded-md transition-colors"
      title="Copier le message"
    >
      {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
    </button>
  )
}

export default function ChatPage() {
  const { user } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocId, setSelectedDocId] = useState<number | undefined>()
  
  const sessionParam = searchParams.get('session')
  const [selectedSessionId, setSelectedSessionId] = useState<number | undefined>(
    sessionParam ? parseInt(sessionParam) : undefined
  )
  
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  useEffect(() => {
    documentsApi.list().then((r) =>
      setDocuments(r.data.documents.filter((d) => d.status === 'ready'))
    )
  }, [])

  useEffect(() => {
    const sId = searchParams.get('session')
    const parsedSId = sId ? parseInt(sId) : undefined
    setSelectedSessionId(parsedSId)
    
    // Also support starting a new chat with a specific doc from the URL
    const dId = searchParams.get('doc')
    const parsedDId = dId ? parseInt(dId) : undefined
    if (parsedDId && !parsedSId) {
       setSelectedDocId(parsedDId)
    }

    if (parsedSId) {
      loadHistory(parsedSId)
    } else {
      setMessages([])
    }
  }, [searchParams])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadHistory = async (sessionId: number) => {
    try {
      const res = await chatApi.history(sessionId)
      const msgs: Message[] = res.data.messages.map((m: ConversationMessage) => ({
        role: m.role,
        content: m.content,
        sources: m.sources ? JSON.parse(m.sources) : undefined,
      }))
      setMessages(msgs)
    } catch { setMessages([]) }
  }

  // Polling automatique pour les documents en 'processing'
  useEffect(() => {
    const processingDocs = documents.filter(d => d.status === 'processing')
    if (processingDocs.length === 0) return

    const poll = setInterval(async () => {
      try {
        const res = await documentsApi.list()
        const newDocs = res.data.documents.filter(d => 
          d.status === 'ready' || processingDocs.some(p => p.id === d.id)
        )
        setDocuments(newDocs)
      } catch (e) {}
    }, 3000)

    return () => clearInterval(poll)
  }, [documents])

  const handleDocChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value ? parseInt(e.target.value) : undefined
    setSelectedDocId(val)
  }

  const startNewChat = () => {
    setSearchParams({})
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploadProgress(0)
      const res = await documentsApi.upload(file, (pct) => setUploadProgress(pct))
      
      const listRes = await documentsApi.list()
      const readyDocs = listRes.data.documents.filter(d => d.status === 'ready' || d.id === res.data.document_id)
      setDocuments(readyDocs)
      
      // Start a new chat session with this doc
      setSelectedDocId(res.data.document_id)
      setSearchParams({ doc: String(res.data.document_id) })
      
    } catch {
      alert("Erreur lors de l'upload du document.")
    } finally {
      setUploadProgress(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')
    setLoading(true)

    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      const token = localStorage.getItem('token')
      const params = new URLSearchParams({ q: question })
      if (selectedSessionId) params.append('session_id', String(selectedSessionId))
      if (selectedDocId) params.append('document_id', String(selectedDocId))

      const response = await fetch(`/api/chat/stream?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let newSessionId: number | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n').filter((l) => l.startsWith('data: '))

        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.session_id && !selectedSessionId && !newSessionId) {
               newSessionId = data.session_id
            }
            if (!data.done) {
              fullContent += data.token
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: fullContent,
                  streaming: true
                }
                return updated
              })
            } else {
              setMessages((prev) => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: fullContent,
                  streaming: false
                }
                return updated
              })
            }
          } catch { /* ignore parse errors */ }
        }
      }
      
      // Update URL with the new session ID so history works
      if (newSessionId && !selectedSessionId) {
         setSearchParams({ session: String(newSessionId) })
         // Trigger a sidebar refresh by dispatching a custom event, or relying on Sidebar polling
         window.dispatchEvent(new Event('chatSessionCreated'))
      }

    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: 'Une erreur est survenue. Veuillez réessayer.',
          streaming: false
        }
        return updated
      })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearHistory = async () => {
    if (selectedSessionId) {
      await chatApi.deleteSession(selectedSessionId)
      window.dispatchEvent(new Event('chatSessionCreated')) // trigger refresh
      setSearchParams({})
    }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 bg-white flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">
            {selectedSessionId ? "Session de discussion" : "Nouvelle discussion"}
          </h1>
          <p className="text-xs text-gray-400">Posez des questions à l'IA</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={startNewChat}
            className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 bg-primary-50 px-3 py-2 rounded-lg transition-colors font-medium"
          >
            <MessageSquarePlus size={16} />
            Nouveau Chat
          </button>
          
          <div className="h-6 w-px bg-gray-200 mx-1"></div>

          {/* Sélecteur de document (Contexte) */}
          <select
            value={selectedDocId ?? ''}
            onChange={handleDocChange}
            disabled={!!selectedSessionId} // On ne change pas le doc en plein milieu d'une session
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none
                       focus:ring-2 focus:ring-primary-500 max-w-[220px] text-gray-700 disabled:opacity-50 disabled:bg-gray-50"
            title={selectedSessionId ? "Le contexte documentaire est fixe pour une session en cours" : "Choisir un document comme contexte"}
          >
            <option value="">Contexte global (Tous docs)</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title_suggested || d.original_name} {d.status === 'processing' ? '(Traitement...)' : ''}
              </option>
            ))}
          </select>
          {selectedSessionId && (
            <button
              onClick={clearHistory}
              className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              title="Supprimer cette discussion"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary-50 flex items-center justify-center mb-4">
              <BookOpen size={28} className="text-primary-400" />
            </div>
            <h3 className="font-medium text-gray-700 mb-1">Prêt pour vos questions</h3>
            <p className="text-sm text-gray-400 max-w-sm">
              Commencez une discussion globale ou sélectionnez un document spécifique.
              Les formules mathématiques sont supportées.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center
                              text-primary-700 text-xs font-bold shrink-0 mr-3 mt-0.5">
                AI
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary-600 text-white rounded-tr-sm'
                  : 'bg-white border border-gray-100 text-gray-800 rounded-tl-sm shadow-sm'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div className="relative group">
                  <div className="prose prose-sm max-w-none pr-8">
                    <ReactMarkdown
                      remarkPlugins={[remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {msg.content}
                    </ReactMarkdown>
                    {msg.streaming && (
                      <span className="inline-block w-0.5 h-4 bg-primary-400 cursor-blink ml-0.5" />
                    )}
                  </div>
                  {!msg.streaming && (
                    <div className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      <CopyButton text={msg.content} />
                    </div>
                  )}
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center
                              text-white text-xs font-bold shrink-0 ml-3 mt-0.5">
                {user?.username[0].toUpperCase()}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-100 bg-white">
        <div className="flex items-end gap-3">
          <input
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.eml"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || uploadProgress !== null}
            className="p-3 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-xl transition-colors disabled:opacity-50"
            title="Ajouter et discuter avec un document"
          >
            {uploadProgress !== null ? (
              <div className="relative flex items-center justify-center">
                <Loader2 size={20} className="animate-spin text-primary-500" />
                <span className="absolute text-[8px] font-bold text-primary-600">{uploadProgress}%</span>
              </div>
            ) : (
              <Paperclip size={20} />
            )}
          </button>
          
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              documents.find(d => d.id === selectedDocId)?.status === 'processing'
                ? "Traitement du document en cours, veuillez patienter..."
                : "Posez une question... (Entrée pour envoyer, Maj+Entrée pour saut de ligne)"
            }
            rows={2}
            className="flex-1 resize-none input py-2.5 text-sm"
            disabled={loading || documents.find(d => d.id === selectedDocId)?.status === 'processing'}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading || documents.find(d => d.id === selectedDocId)?.status === 'processing'}
            className="btn-primary p-3 shrink-0"
          >
            {loading
              ? <Loader2 size={18} className="animate-spin" />
              : <Send size={18} />
            }
          </button>
        </div>
      </div>
    </div>
  )
}
