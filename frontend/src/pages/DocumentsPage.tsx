import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FolderOpen, FileText, Download, Trash2, MessageSquare,
  Search, RefreshCw, AlertCircle, Loader2, CheckCircle
} from 'lucide-react'
import { documentsApi, Document } from '@/lib/api'
import { useDocumentsStore } from '@/store/documentsStore'
import clsx from 'clsx'
import DocumentViewer from '@/components/DocumentViewer'

const STATUS_CONFIG = {
  ready:      { label: 'Prêt',        icon: CheckCircle, color: 'text-green-500' },
  processing: { label: 'Traitement',  icon: Loader2,     color: 'text-blue-500'  },
  pending:    { label: 'En attente',  icon: Loader2,     color: 'text-gray-400'  },
  error:      { label: 'Erreur',      icon: AlertCircle, color: 'text-red-500'   },
}

const SUBJECT_COLORS: Record<string, string> = {
  Mathématiques: 'bg-blue-100 text-blue-700',
  Physique:      'bg-purple-100 text-purple-700',
  Informatique:  'bg-green-100 text-green-700',
  Chimie:        'bg-orange-100 text-orange-700',
  Histoire:      'bg-yellow-100 text-yellow-700',
  Langues:       'bg-pink-100 text-pink-700',
  Autre:         'bg-gray-100 text-gray-600',
}

export default function DocumentsPage() {
  const navigate = useNavigate()
  const { documents, loading, fetchDocuments, removeDocument, setFilter } = useDocumentsStore()
  const [search, setSearch] = useState('')
  const [subjectFilter, setSubjectFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [deleting, setDeleting] = useState<number | null>(null)
  const [renaming, setRenaming] = useState<number | null>(null)
  const [newName, setNewName] = useState('')
  const [viewing, setViewing] = useState<Document | null>(null)

  useEffect(() => { fetchDocuments() }, [])

  const subjects = [...new Set(documents.map((d) => d.subject).filter(Boolean))] as string[]
  const types    = [...new Set(documents.map((d) => d.doc_type).filter(Boolean))] as string[]

  const filtered = documents.filter((d) => {
    const matchSearch = !search ||
      d.original_name.toLowerCase().includes(search.toLowerCase()) ||
      d.title_suggested?.toLowerCase().includes(search.toLowerCase())
    const matchSubject = !subjectFilter || d.subject === subjectFilter
    const matchType    = !typeFilter    || d.doc_type === typeFilter
    return matchSearch && matchSubject && matchType
  })

  // Grouper par matière
  const grouped = filtered.reduce<Record<string, Document[]>>((acc, doc) => {
    const key = doc.subject || 'Non classifié'
    if (!acc[key]) acc[key] = []
    acc[key].push(doc)
    return acc
  }, {})

  const handleDelete = async (id: number) => {
    if (!confirm('Supprimer ce document ? Cette action est irréversible.')) return
    setDeleting(id)
    try {
      await documentsApi.delete(id)
      removeDocument(id)
    } finally {
      setDeleting(null)
    }
  }

  const handleDownload = async (doc: Document) => {
    const res = await documentsApi.downloadUrl(doc.id)
    window.open(res.data.url, '_blank')
  }

  const handleRename = async (id: number) => {
    if (!newName.trim()) return
    await documentsApi.rename(id, newName.trim())
    setRenaming(null)
    fetchDocuments()
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Mes documents</h1>
          <p className="text-gray-500 text-sm mt-0.5">{documents.length} document(s) indexé(s)</p>
        </div>
        <button onClick={() => fetchDocuments()} className="btn-secondary flex items-center gap-2">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          Actualiser
        </button>
      </div>

      {/* Filtres */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9"
            placeholder="Rechercher..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="input w-auto"
          value={subjectFilter}
          onChange={(e) => setSubjectFilter(e.target.value)}
        >
          <option value="">Toutes les matières</option>
          {subjects.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select
          className="input w-auto"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">Tous les types</option>
          {types.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>

      {/* Arborescence par matière */}
      {loading && documents.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={24} className="text-gray-300 animate-spin" />
        </div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="text-center py-20">
          <FolderOpen size={40} className="mx-auto text-gray-200 mb-3" />
          <p className="text-gray-400">Aucun document trouvé</p>
          <button onClick={() => navigate('/upload')} className="btn-primary mt-4 text-sm">
            Uploader un document
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([subject, docs]) => (
            <div key={subject}>
              <div className="flex items-center gap-2 mb-3">
                <FolderOpen size={17} className="text-primary-500" />
                <h2 className="font-semibold text-gray-800">{subject}</h2>
                <span className="badge bg-gray-100 text-gray-500">{docs.length}</span>
              </div>

              <div className="space-y-2 ml-6">
                {docs.map((doc) => {
                  const StatusIcon = STATUS_CONFIG[doc.status]?.icon ?? FileText
                  const statusColor = STATUS_CONFIG[doc.status]?.color ?? 'text-gray-400'

                  return (
                    <div key={doc.id} className="card px-4 py-3 flex items-center gap-3 group">
                      <FileText size={16} className="text-gray-400 shrink-0" />

                      <div className="flex-1 min-w-0">
                        {renaming === doc.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              autoFocus
                              className="input text-sm py-1"
                              value={newName}
                              onChange={(e) => setNewName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleRename(doc.id)
                                if (e.key === 'Escape') setRenaming(null)
                              }}
                            />
                            <button onClick={() => handleRename(doc.id)} className="btn-primary text-xs px-3 py-1">OK</button>
                            <button onClick={() => setRenaming(null)} className="btn-secondary text-xs px-3 py-1">Annuler</button>
                          </div>
                        ) : (
                          <p
                            className="text-sm font-medium text-gray-800 truncate cursor-pointer hover:text-primary-600"
                            onClick={() => {
                                if(doc.status === 'ready') setViewing(doc);
                            }}
                            onDoubleClick={(e) => { 
                                e.stopPropagation()
                                setRenaming(doc.id); 
                                setNewName(doc.original_name) 
                            }}
                            title="Cliquer pour voir, double-cliquer pour renommer"
                          >
                            {doc.title_suggested || doc.original_name}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-0.5">
                          {doc.doc_type && (
                            <span className="badge bg-gray-100 text-gray-500 text-xs">{doc.doc_type}</span>
                          )}
                          {doc.language && (
                            <span className="text-xs text-gray-400 uppercase">{doc.language}</span>
                          )}
                          <span className="text-xs text-gray-400">
                            {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                          </span>
                          <div className={`flex items-center gap-1 ${statusColor}`}>
                            <StatusIcon size={12} className={doc.status === 'processing' ? 'animate-spin' : ''} />
                            <span className="text-xs">{STATUS_CONFIG[doc.status]?.label}</span>
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => navigate(`/chat?doc=${doc.id}`)}
                          className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-md transition-colors"
                          title="Interroger ce document"
                        >
                          <MessageSquare size={15} />
                        </button>
                        <button
                          onClick={() => handleDownload(doc)}
                          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
                          title="Télécharger"
                        >
                          <Download size={15} />
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          disabled={deleting === doc.id}
                          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                          title="Supprimer"
                        >
                          {deleting === doc.id
                            ? <Loader2 size={15} className="animate-spin" />
                            : <Trash2 size={15} />
                          }
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Document Viewer */}
      {viewing && (
        <DocumentViewer document={viewing} onClose={() => setViewing(null)} />
      )}
    </div>
  )
}
