import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, CheckCircle, XCircle, Loader2, ArrowRight, Wifi, WifiOff } from 'lucide-react'
import { documentsApi } from '@/lib/api'
import { useDocumentsStore } from '@/store/documentsStore'
import { useAuthStore } from '@/store/authStore'
import clsx from 'clsx'

// ─── Types ────────────────────────────────────────────────────────────────────

interface WsEvent {
  status: 'processing' | 'completed' | 'error'
  document_id: number
  message: string
  subject?: string
  doc_type?: string
  language?: string
  num_chunks?: number
}

interface UploadState {
  file: File
  progress: number
  status: 'uploading' | 'processing' | 'done' | 'error'
  documentId?: number
  result?: Record<string, unknown>
  error?: string
}

// ─── Constantes ───────────────────────────────────────────────────────────────

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'text/plain': ['.txt'],
  'message/rfc822': ['.eml'],
}

const SUBJECT_COLORS: Record<string, string> = {
  Mathématiques: 'bg-blue-100 text-blue-700',
  Physique: 'bg-purple-100 text-purple-700',
  Informatique: 'bg-green-100 text-green-700',
  Chimie: 'bg-orange-100 text-orange-700',
  Histoire: 'bg-yellow-100 text-yellow-700',
  Autre: 'bg-gray-100 text-gray-600',
}

// ─── Composant ────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const navigate = useNavigate()
  const { addDocument } = useDocumentsStore()
  const { user } = useAuthStore()

  const [uploads, setUploads] = useState<UploadState[]>([])
  const [wsConnected, setWsConnected] = useState(false)

  // ── Refs WebSocket ──
  // Une seule connexion WS partagée pour tous les uploads de la session
  const wsRef = useRef<WebSocket | null>(null)
  // Map document_id → index dans le tableau `uploads`
  const docIndexMapRef = useRef<Record<number, number>>({})
  // Map document_id → clearInterval (fallback polling)
  const pollTimersRef = useRef<Record<number, ReturnType<typeof setInterval>>>({})
  // Compteur d'uploads en attente de résolution (processing)
  const pendingCountRef = useRef(0)

  // Nettoyage à la destruction du composant
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      Object.values(pollTimersRef.current).forEach(clearInterval)
    }
  }, [])

  // ── Mise à jour d'un upload par index ──
  const updateUpload = useCallback(
    (index: number, patch: Partial<UploadState>) =>
      setUploads((prev) => prev.map((u, i) => (i === index ? { ...u, ...patch } : u))),
    []
  )

  // ── Mise à jour d'un upload par documentId ──
  const updateUploadByDocId = useCallback(
    (documentId: number, patch: Partial<UploadState>) => {
      setUploads((prev) =>
        prev.map((u) => (u.documentId === documentId ? { ...u, ...patch } : u))
      )
    },
    []
  )

  // ── Fallback polling pour un document précis ──
  const startPollingForDoc = useCallback(
    (docId: number) => {
      if (pollTimersRef.current[docId]) return // déjà en cours
      let attempts = 0
      const timer = setInterval(async () => {
        attempts++
        try {
          const res = await documentsApi.get(docId)
          const doc = res.data
          if (doc.status === 'ready') {
            clearInterval(timer)
            delete pollTimersRef.current[docId]
            addDocument(doc)
            updateUploadByDocId(docId, { status: 'done', result: doc as unknown as Record<string, unknown> })
            pendingCountRef.current = Math.max(0, pendingCountRef.current - 1)
          } else if (doc.status === 'error' || attempts > 60) {
            clearInterval(timer)
            delete pollTimersRef.current[docId]
            updateUploadByDocId(docId, { status: 'error', error: 'Échec du traitement' })
            pendingCountRef.current = Math.max(0, pendingCountRef.current - 1)
          }
        } catch {
          clearInterval(timer)
          delete pollTimersRef.current[docId]
          updateUploadByDocId(docId, { status: 'error', error: 'Erreur de communication' })
          pendingCountRef.current = Math.max(0, pendingCountRef.current - 1)
        }
      }, 3000)
      pollTimersRef.current[docId] = timer
    },
    [addDocument, updateUploadByDocId]
  )

  // ── Bascule en mode fallback polling pour tous les docs encore en "processing" ──
  const fallbackToPolling = useCallback(() => {
    setWsConnected(false)
    setUploads((prev) => {
      prev.forEach((u) => {
        if (u.status === 'processing' && u.documentId !== undefined) {
          startPollingForDoc(u.documentId)
        }
      })
      return prev
    })
  }, [startPollingForDoc])

  // ── Ferme le WS si plus rien à attendre ──
  const maybeCloseWs = useCallback(() => {
    if (pendingCountRef.current <= 0 && wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
      setWsConnected(false)
    }
  }, [])

  // ── Gestion des événements WebSocket ──
  const handleWsMessage = useCallback(
    (event: MessageEvent) => {
      let data: WsEvent
      try {
        data = JSON.parse(event.data as string) as WsEvent
      } catch {
        return
      }

      const docId = data.document_id

      // Annule le polling si on en avait lancé un en parallèle
      if (pollTimersRef.current[docId]) {
        clearInterval(pollTimersRef.current[docId])
        delete pollTimersRef.current[docId]
      }

      if (data.status === 'completed') {
        // Récupère les détails complets depuis l'API pour garantir la cohérence
        documentsApi
          .get(docId)
          .then((res) => {
            addDocument(res.data)
            updateUploadByDocId(docId, {
              status: 'done',
              result: res.data as unknown as Record<string, unknown>,
            })
          })
          .catch(() => {
            // Si le GET échoue, on utilise le payload WS directement
            updateUploadByDocId(docId, { status: 'done', result: data as unknown as Record<string, unknown> })
          })
          .finally(() => {
            pendingCountRef.current = Math.max(0, pendingCountRef.current - 1)
            maybeCloseWs()
          })
      } else if (data.status === 'error') {
        updateUploadByDocId(docId, { status: 'error', error: data.message })
        pendingCountRef.current = Math.max(0, pendingCountRef.current - 1)
        maybeCloseWs()
      }
    },
    [addDocument, updateUploadByDocId, maybeCloseWs]
  )

  // ── Connexion WebSocket (lazy, réutilisée) ──
  const ensureWsConnected = useCallback(() => {
    const token = localStorage.getItem('token')
    const userId = user?.id
    if (!token || userId === undefined) return

    // Déjà connecté et fonctionnel
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    // Connexion en cours
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) return

    const wsUrl = `/ws/${userId}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setWsConnected(true)
    }

    ws.onmessage = handleWsMessage

    ws.onerror = () => {
      setWsConnected(false)
      fallbackToPolling()
    }

    ws.onclose = (ev) => {
      setWsConnected(false)
      wsRef.current = null
      // Si fermeture anormale ET des docs encore en attente → polling
      if (ev.code !== 1000) {
        fallbackToPolling()
      }
    }

    wsRef.current = ws
  }, [user?.id, handleWsMessage, fallbackToPolling])

  // ── Pipeline d'upload pour un fichier ──
  const processFile = useCallback(
    async (file: File, index: number) => {
      try {
        const res = await documentsApi.upload(file, (pct) =>
          updateUpload(index, { progress: pct })
        )

        const docId: number = res.data.document_id

        // Enregistrer la correspondance docId ↔ index ET sur l'état
        docIndexMapRef.current[docId] = index
        pendingCountRef.current++
        updateUpload(index, { status: 'processing', progress: 100, documentId: docId, result: res.data })

        // Tenter la connexion WebSocket
        ensureWsConnected()

        // Délai de grâce : si le WS n'est pas connecté dans 5 s, démarrer le polling
        setTimeout(() => {
          if (
            !wsRef.current ||
            wsRef.current.readyState !== WebSocket.OPEN
          ) {
            // WS non disponible → polling direct
            setUploads((prev) => {
              const u = prev[index]
              if (u?.status === 'processing' && u.documentId !== undefined) {
                startPollingForDoc(u.documentId)
              }
              return prev
            })
          }
        }, 5000)
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        updateUpload(index, {
          status: 'error',
          error: axiosErr.response?.data?.detail ?? 'Erreur upload',
        })
      }
    },
    [updateUpload, ensureWsConnected, startPollingForDoc]
  )

  // ── Drop zone ──
  const onDrop = useCallback(
    (accepted: File[]) => {
      const startIndex = uploads.length
      const newUploads: UploadState[] = accepted.map((f) => ({
        file: f,
        progress: 0,
        status: 'uploading',
      }))
      setUploads((prev) => [...prev, ...newUploads])
      accepted.forEach((file, i) => processFile(file, startIndex + i))
    },
    [uploads.length, processFile]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: 50 * 1024 * 1024,
  })

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* En-tête */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-1">Uploader des documents</h1>
          <p className="text-gray-500 text-sm">
            PDF, DOCX, JPG, PNG, TXT, EML — max 50 Mo par fichier
          </p>
        </div>

        {/* Indicateur de connexion WS */}
        {uploads.some((u) => u.status === 'processing') && (
          <div
            className={clsx(
              'flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border',
              wsConnected
                ? 'text-green-700 bg-green-50 border-green-200'
                : 'text-orange-600 bg-orange-50 border-orange-200'
            )}
            title={wsConnected ? 'Notifications temps réel actives' : 'Mode polling (fallback)'}
          >
            {wsConnected ? (
              <>
                <Wifi size={13} />
                Temps réel
              </>
            ) : (
              <>
                <WifiOff size={13} />
                Polling
              </>
            )}
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={clsx(
          'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-primary-400 bg-primary-50'
            : 'border-gray-200 hover:border-primary-300 hover:bg-gray-50'
        )}
      >
        <input {...getInputProps()} />
        <Upload
          size={36}
          className={clsx('mx-auto mb-3', isDragActive ? 'text-primary-500' : 'text-gray-300')}
        />
        <p className="font-medium text-gray-700">
          {isDragActive ? 'Déposez les fichiers ici' : 'Glissez-déposez vos fichiers'}
        </p>
        <p className="text-sm text-gray-400 mt-1">ou cliquez pour sélectionner</p>
      </div>

      {/* Liste des uploads */}
      {uploads.length > 0 && (
        <div className="mt-6 space-y-3">
          {uploads.map((u, i) => (
            <div key={i} className="card p-4">
              <div className="flex items-start gap-3">
                <FileText size={18} className="text-gray-400 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{u.file.name}</p>
                  <p className="text-xs text-gray-400">
                    {(u.file.size / 1024 / 1024).toFixed(1)} Mo
                  </p>

                  {/* Barre de progression — upload HTTP */}
                  {u.status === 'uploading' && (
                    <div className="mt-2">
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary-500 rounded-full transition-all duration-300"
                          style={{ width: `${u.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-400 mt-1">Upload : {u.progress}%</p>
                    </div>
                  )}

                  {/* Traitement en cours */}
                  {u.status === 'processing' && (
                    <div className="flex items-center gap-2 mt-2">
                      <Loader2 size={13} className="text-primary-500 animate-spin" />
                      <span className="text-xs text-primary-600">
                        Traitement en cours...
                      </span>
                    </div>
                  )}

                  {/* Succès */}
                  {u.status === 'done' && u.result && (
                    <div className="mt-2 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-green-500" />
                        <span className="text-xs text-green-600 font-medium">
                          Traitement terminé
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {(u.result.subject as string | undefined) && (
                          <span
                            className={`badge ${
                              SUBJECT_COLORS[u.result.subject as string] ?? SUBJECT_COLORS['Autre']
                            }`}
                          >
                            {u.result.subject as string}
                          </span>
                        )}
                        {(u.result.doc_type as string | undefined) && (
                          <span className="badge bg-gray-100 text-gray-600">
                            {u.result.doc_type as string}
                          </span>
                        )}
                        {(u.result.language as string | undefined) && (
                          <span className="badge bg-gray-100 text-gray-500 uppercase">
                            {u.result.language as string}
                          </span>
                        )}
                        {(u.result.num_chunks as number | undefined) !== undefined &&
                          (u.result.num_chunks as number) > 0 && (
                            <span className="badge bg-gray-100 text-gray-500">
                              {u.result.num_chunks as number} chunks
                            </span>
                          )}
                      </div>
                    </div>
                  )}

                  {/* Erreur */}
                  {u.status === 'error' && (
                    <div className="flex items-center gap-2 mt-2">
                      <XCircle size={13} className="text-red-500" />
                      <span className="text-xs text-red-500">{u.error}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CTA vers la bibliothèque */}
      {uploads.some((u) => u.status === 'done') && (
        <button
          onClick={() => navigate('/documents')}
          className="btn-primary mt-6 flex items-center gap-2"
        >
          Voir mes documents
          <ArrowRight size={16} />
        </button>
      )}
    </div>
  )
}
