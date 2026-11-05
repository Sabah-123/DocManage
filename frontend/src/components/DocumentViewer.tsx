import { useState, useEffect, useRef, useMemo } from 'react'
import { X, Loader2, Download, AlertCircle } from 'lucide-react'
import * as pdfjsLib from 'pdfjs-dist'
import { documentsApi, Document } from '@/lib/api'

// Configuration de pdfjs-dist pour pointer sur le worker copié dans le dossier public
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js'

interface DocumentViewerProps {
  document: Document
  onClose: () => void
}

export default function DocumentViewer({ document, onClose }: DocumentViewerProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [contentUrl, setContentUrl] = useState<string | null>(null)
  const [textContent, setTextContent] = useState<string | null>(null)
  const [pdfNumPages, setPdfNumPages] = useState<number | null>(null)
  const [pdfPage, setPdfPage] = useState(1)

  const pdfCanvasRef = useRef<HTMLCanvasElement>(null)
  const pdfDocRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null)

  // ─── Chargement du document (URL ou Texte) ──────────────────────────────
  useEffect(() => {
    let active = true

    async function fetchDoc() {
      try {
        setLoading(true)
        setError(null)

        const ext = document.file_type.toLowerCase()

        // 1. PDF / Images → Récupération d'une URL presignée
        if (['pdf', 'jpg', 'jpeg', 'png'].includes(ext)) {
          const res = await documentsApi.downloadUrl(document.id)
          if (active) setContentUrl(res.data.url)
        }
        // 2. Texte brut / DOCX → Récupération du contenu extrait via l'API
        else if (['txt', 'docx'].includes(ext)) {
          // Utilise un client HTTP axios basique si l'endpoint custom n'est pas typé
          const res = await documentsApi.get(document.id).then(r => documentsApi.summary(r.data.id).then(() => documentsApi.get(document.id).then(() => import('@/lib/api').then(api => api.default.get<{content: string}>(`/documents/${document.id}/content`)))))
          if (active) setTextContent(res.data.content)
        } else {
           if (active) setError("Format non supporté pour la prévisualisation")
        }

      } catch (err) {
        if (active) {
            console.error("DocumentViewer error:", err)
            setError('Impossible de charger le document.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    fetchDoc()
    return () => { active = false }
  }, [document.id, document.file_type])


  // ─── Rendu PDF ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (document.file_type.toLowerCase() !== 'pdf' || !contentUrl || !pdfCanvasRef.current) return

    let active = true
    let renderTask: pdfjsLib.RenderTask | null = null

    async function loadAndRenderPdf() {
      try {
        if (!pdfDocRef.current) {
            const loadingTask = pdfjsLib.getDocument(contentUrl as string)
            const pdfDoc = await loadingTask.promise
            if(!active) return;
            pdfDocRef.current = pdfDoc
            setPdfNumPages(pdfDoc.numPages)
        }

        const pdfDoc = pdfDocRef.current
        const page = await pdfDoc.getPage(pdfPage)
        if(!active) return;

        const viewport = page.getViewport({ scale: 1.5 })
        const canvas = pdfCanvasRef.current
        if (!canvas) return
        
        const context = canvas.getContext('2d')
        if (!context) return
        
        canvas.height = viewport.height
        canvas.width = viewport.width

        const renderContext = {
          canvasContext: context,
          viewport: viewport,
        }

        renderTask = page.render(renderContext)
        await renderTask.promise
      } catch (err: any) {
        // Ignorer les erreurs d'annulation (quand on change de page très vite)
        if (err.name === 'RenderingCancelledException') return;
        if (active) {
             console.error('Erreur rendu PDF:', err)
             setError('Erreur lors de l\'affichage du PDF.')
        }
      }
    }

    loadAndRenderPdf()

    return () => {
      active = false
      if (renderTask) renderTask.cancel()
    }
  }, [contentUrl, pdfPage, document.file_type])


  // ─── Helpers Rendering ──────────────────────────────────────────────────
  
  const ext = document.file_type.toLowerCase()
  const isPdf = ext === 'pdf'
  const isImage = ['jpg', 'jpeg', 'png'].includes(ext)
  const isText = ['txt', 'docx'].includes(ext)


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      
      {/* Conteneur modale */}
      <div 
        className="relative flex flex-col w-full max-w-5xl h-full max-h-[90vh] bg-white rounded-xl shadow-2xl overflow-hidden" 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50/80">
          <div className="min-w-0 pr-4">
             <h3 className="text-lg font-semibold text-gray-900 truncate">
                {document.title_suggested || document.original_name}
             </h3>
             <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                <span className="uppercase">{ext}</span>
                <span>•</span>
                <span>{(document.num_chunks || 0)} chunks indexés</span>
             </div>
          </div>
          
          <div className="flex items-center gap-2 shrink-0">
              {contentUrl && (
                  <button 
                    onClick={() => window.open(contentUrl, '_blank')}
                    className="p-2 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title="Télécharger"
                  >
                     <Download size={18} />
                  </button>
              )}
             <button 
                onClick={onClose}
                className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                title="Fermer"
              >
                 <X size={18} />
             </button>
          </div>
        </div>

        {/* Corps du Viewer */}
        <div className="flex-1 overflow-auto bg-gray-100 relative">
           
           {/* Loader global */}
           {loading && (
               <div className="absolute inset-0 flex items-center justify-center bg-gray-100/80 z-10">
                   <Loader2 size={32} className="animate-spin text-primary-500" />
               </div>
           )}

           {/* Erreur */}
           {error && !loading && (
               <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                   <AlertCircle size={48} className="text-red-400 mb-4" />
                   <p className="text-red-600 font-medium">{error}</p>
               </div>
           )}

           {/* Viewer Image */}
           {isImage && contentUrl && !loading && !error && (
               <div className="flex items-center justify-center h-full p-4">
                   <img 
                      src={contentUrl} 
                      alt={document.original_name} 
                      className="max-w-full max-h-full object-contain rounded shadow-sm bg-white" 
                   />
               </div>
           )}

           {/* Viewer Texte / DOCX */}
           {isText && textContent && !loading && !error && (
               <div className="max-w-3xl mx-auto p-8 my-4 bg-white rounded shadow-sm font-serif text-gray-800 leading-relaxed whitespace-pre-wrap">
                   {textContent}
               </div>
           )}

           {/* Viewer PDF */}
           {isPdf && contentUrl && !loading && !error && (
               <div className="flex flex-col items-center py-6">
                   <canvas 
                      ref={pdfCanvasRef} 
                      className="bg-white shadow-md rounded"
                      style={{ maxWidth: '100%', height: 'auto' }}
                   />
               </div>
           )}

        </div>

        {/* Footer (Contrôles PDF) */}
        {isPdf && pdfNumPages && !loading && !error && (
            <div className="flex items-center justify-center gap-4 px-5 py-3 border-t border-gray-200 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                <button 
                  disabled={pdfPage <= 1}
                  onClick={() => setPdfPage(p => p - 1)}
                  className="btn-secondary px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Précédent
                </button>
                <span className="text-sm font-medium text-gray-700">
                    Page {pdfPage} sur {pdfNumPages}
                </span>
                <button 
                  disabled={pdfPage >= pdfNumPages}
                  onClick={() => setPdfPage(p => p + 1)}
                  className="btn-secondary px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Suivant
                </button>
            </div>
        )}

      </div>
    </div>
  )
}
