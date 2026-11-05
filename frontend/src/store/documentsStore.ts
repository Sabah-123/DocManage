import { create } from 'zustand'
import { Document, documentsApi } from '@/lib/api'

interface DocumentsState {
  documents: Document[]
  loading: boolean
  selectedDoc: Document | null
  filter: { subject?: string; doc_type?: string }

  fetchDocuments: () => Promise<void>
  setFilter: (filter: { subject?: string; doc_type?: string }) => void
  selectDocument: (doc: Document | null) => void
  removeDocument: (id: number) => void
  updateDocument: (doc: Document) => void
  addDocument: (doc: Document) => void
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  loading: false,
  selectedDoc: null,
  filter: {},

  fetchDocuments: async () => {
    set({ loading: true })
    try {
      const res = await documentsApi.list(get().filter)
      set({ documents: res.data.documents })
    } finally {
      set({ loading: false })
    }
  },

  setFilter: (filter) => {
    set({ filter })
    get().fetchDocuments()
  },

  selectDocument: (doc) => set({ selectedDoc: doc }),

  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
      selectedDoc: state.selectedDoc?.id === id ? null : state.selectedDoc,
    })),

  updateDocument: (doc) =>
    set((state) => ({
      documents: state.documents.map((d) => (d.id === doc.id ? doc : d)),
      selectedDoc: state.selectedDoc?.id === doc.id ? doc : state.selectedDoc,
    })),

  addDocument: (doc) =>
    set((state) => ({ documents: [doc, ...state.documents] })),
}))
