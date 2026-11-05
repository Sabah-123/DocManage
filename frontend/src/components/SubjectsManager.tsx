import { useState, useEffect, useRef } from 'react'
import {
  Plus, Pencil, Trash2, RotateCcw, Check, X, Loader2, BookOpen,
} from 'lucide-react'
import { subjectsApi, Subject, SubjectCreate } from '@/lib/api'

// ─── Palette de couleurs prédéfinies ─────────────────────────────────────────
const COLOR_PALETTE = [
  '#4F46E5', '#0EA5E9', '#10B981', '#F59E0B',
  '#8B5CF6', '#EC4899', '#14B8A6', '#22C55E',
  '#EF4444', '#F97316', '#6B7280', '#1D4ED8',
]

// ─── Composant inline color picker ───────────────────────────────────────────
interface ColorPickerProps {
  value: string
  onChange: (color: string) => void
}

function ColorPicker({ value, onChange }: ColorPickerProps) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {COLOR_PALETTE.map((c) => (
        <button
          key={c}
          type="button"
          title={c}
          onClick={() => onChange(c)}
          className="w-6 h-6 rounded-full border-2 transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary-500"
          style={{
            backgroundColor: c,
            borderColor: value === c ? '#1e40af' : 'transparent',
          }}
        />
      ))}
      {/* Couleur personnalisée */}
      <input
        type="color"
        value={value || '#6B7280'}
        onChange={(e) => onChange(e.target.value)}
        title="Couleur personnalisée"
        className="w-6 h-6 rounded-full cursor-pointer border border-gray-200 p-0 overflow-hidden"
        style={{ appearance: 'none' }}
      />
    </div>
  )
}

// ─── Ligne matière (mode lecture) ────────────────────────────────────────────
interface SubjectRowProps {
  subject: Subject
  onEdit: () => void
  onDelete: () => void
}

function SubjectRow({ subject, onEdit, onDelete }: SubjectRowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-gray-50 transition-colors group">
      {/* Pastille couleur + icône */}
      <span
        className="w-9 h-9 rounded-lg flex items-center justify-center text-lg shrink-0"
        style={{ backgroundColor: subject.color ? `${subject.color}20` : '#f3f4f6' }}
      >
        {subject.icon ?? '📁'}
      </span>

      {/* Nom */}
      <span className="flex-1 text-sm font-medium text-gray-800">{subject.name}</span>

      {/* Badge "défaut" */}
      {subject.is_default && (
        <span className="badge bg-primary-50 text-primary-600 text-xs hidden sm:inline-flex">
          Défaut
        </span>
      )}

      {/* Rond couleur */}
      <span
        className="w-3 h-3 rounded-full shrink-0"
        style={{ backgroundColor: subject.color ?? '#6B7280' }}
      />

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          className="p-1.5 rounded-md text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
          title="Modifier"
        >
          <Pencil size={14} />
        </button>

        {confirmDelete ? (
          <span className="flex items-center gap-1 ml-1">
            <span className="text-xs text-red-600 font-medium">Supprimer ?</span>
            <button
              onClick={onDelete}
              className="p-1 rounded text-red-600 hover:bg-red-50 transition-colors"
              title="Confirmer"
            >
              <Check size={13} />
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="p-1 rounded text-gray-400 hover:bg-gray-100 transition-colors"
              title="Annuler"
            >
              <X size={13} />
            </button>
          </span>
        ) : (
          <button
            onClick={() => subject.is_default ? undefined : setConfirmDelete(true)}
            disabled={subject.is_default}
            className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={subject.is_default ? 'Impossible de supprimer une matière par défaut' : 'Supprimer'}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Ligne matière (mode édition inline) ─────────────────────────────────────
interface EditRowProps {
  subject: Subject
  onSave: (name: string, color: string, icon: string) => Promise<void>
  onCancel: () => void
}

function EditRow({ subject, onSave, onCancel }: EditRowProps) {
  const [name, setName] = useState(subject.name)
  const [color, setColor] = useState(subject.color ?? '#6B7280')
  const [icon, setIcon] = useState(subject.icon ?? '📁')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSave = async () => {
    if (!name.trim()) { setError('Le nom est requis'); return }
    setSaving(true)
    setError('')
    try {
      await onSave(name.trim(), color, icon)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div className="px-4 py-3 rounded-lg bg-primary-50 border border-primary-200 space-y-2">
      <div className="flex items-center gap-2">
        {/* Icône emoji */}
        <input
          type="text"
          value={icon}
          onChange={(e) => setIcon(e.target.value)}
          maxLength={4}
          className="w-12 text-center border border-gray-200 rounded-lg py-1.5 text-lg focus:outline-none focus:ring-2 focus:ring-primary-400"
          title="Emoji ou icône"
        />
        {/* Nom */}
        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKey}
          maxLength={100}
          placeholder="Nom de la matière"
          className="input flex-1 text-sm"
        />
        {/* Boutons */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="p-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors disabled:opacity-50"
          title="Sauvegarder"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
        </button>
        <button
          onClick={onCancel}
          className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
          title="Annuler"
        >
          <X size={14} />
        </button>
      </div>
      {/* Color picker */}
      <ColorPicker value={color} onChange={setColor} />
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}

// ─── Formulaire ajout nouvelle matière ───────────────────────────────────────
interface AddFormProps {
  onAdd: (data: SubjectCreate) => Promise<void>
  onCancel: () => void
}

function AddForm({ onAdd, onCancel }: AddFormProps) {
  const [name, setName] = useState('')
  const [color, setColor] = useState('#4F46E5')
  const [icon, setIcon] = useState('📁')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSave = async () => {
    if (!name.trim()) { setError('Le nom est requis'); return }
    setSaving(true)
    setError('')
    try {
      await onAdd({ name: name.trim(), color, icon })
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Erreur lors de la création')
      setSaving(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div className="px-4 py-3 rounded-lg bg-green-50 border border-green-200 space-y-2">
      <p className="text-xs font-semibold text-green-700 mb-1">Nouvelle matière</p>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={icon}
          onChange={(e) => setIcon(e.target.value)}
          maxLength={4}
          className="w-12 text-center border border-gray-200 rounded-lg py-1.5 text-lg focus:outline-none focus:ring-2 focus:ring-green-400"
          title="Emoji"
        />
        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKey}
          maxLength={100}
          placeholder="Nom de la matière"
          className="input flex-1 text-sm"
        />
        <button
          onClick={handleSave}
          disabled={saving}
          className="p-2 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50"
          title="Créer"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
        </button>
        <button
          onClick={onCancel}
          className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
          title="Annuler"
        >
          <X size={14} />
        </button>
      </div>
      <ColorPicker value={color} onChange={setColor} />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}

// ─── Composant principal ──────────────────────────────────────────────────────
export default function SubjectsManager() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  // ── Chargement ──
  const fetchSubjects = async () => {
    try {
      setLoading(true)
      setError('')
      const res = await subjectsApi.list()
      setSubjects(res.data)
    } catch {
      setError('Impossible de charger les matières')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSubjects() }, [])

  // ── Édition ──
  const handleSaveEdit = async (id: number, name: string, color: string, icon: string) => {
    const res = await subjectsApi.update(id, { name, color, icon })
    setSubjects((prev) => prev.map((s) => (s.id === id ? res.data : s)))
    setEditingId(null)
  }

  // ── Suppression ──
  const handleDelete = async (id: number) => {
    await subjectsApi.delete(id)
    setSubjects((prev) => prev.filter((s) => s.id !== id))
  }

  // ── Création ──
  const handleAdd = async (data: SubjectCreate) => {
    const res = await subjectsApi.create(data)
    setSubjects((prev) => [...prev, res.data])
    setShowAddForm(false)
  }

  // ── Réinitialisation ──
  const handleReset = async () => {
    setResetting(true)
    try {
      const res = await subjectsApi.reset()
      setSubjects(res.data)
    } catch {
      setError('Erreur lors de la réinitialisation')
    } finally {
      setResetting(false)
      setConfirmReset(false)
      setEditingId(null)
      setShowAddForm(false)
    }
  }

  return (
    <div className="card p-6">
      {/* En-tête */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-primary-500" />
          <h3 className="font-semibold text-gray-800">Mes matières</h3>
          {!loading && (
            <span className="badge bg-gray-100 text-gray-500 text-xs ml-1">
              {subjects.filter(s => !s.is_default).length}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Bouton Réinitialiser */}
          {confirmReset ? (
            <span className="flex items-center gap-1">
              <span className="text-xs text-orange-600 font-medium">Réinitialiser ?</span>
              <button
                onClick={handleReset}
                disabled={resetting}
                className="p-1.5 rounded-lg bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-50"
                title="Confirmer la réinitialisation"
              >
                {resetting ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              </button>
              <button
                onClick={() => setConfirmReset(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 transition-colors"
              >
                <X size={12} />
              </button>
            </span>
          ) : (
            <button
              onClick={() => setConfirmReset(true)}
              className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1.5"
              title="Remettre les 9 matières par défaut"
            >
              <RotateCcw size={13} />
              Réinitialiser
            </button>
          )}

          {/* Bouton Ajouter */}
          {!showAddForm && (
            <button
              onClick={() => { setShowAddForm(true); setEditingId(null) }}
              className="btn-primary text-xs px-3 py-1.5 flex items-center gap-1.5"
            >
              <Plus size={13} />
              Ajouter
            </button>
          )}
        </div>
      </div>

      {/* Erreur globale */}
      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Chargement */}
      {loading ? (
        <div className="flex items-center justify-center py-8 text-gray-400">
          <Loader2 size={22} className="animate-spin mr-2" />
          <span className="text-sm">Chargement des matières…</span>
        </div>
      ) : (
        <div className="space-y-1">
          {/* Formulaire d'ajout */}
          {showAddForm && (
            <AddForm
              onAdd={handleAdd}
              onCancel={() => setShowAddForm(false)}
            />
          )}

          {/* Liste des matières (uniquement celles ajoutées par l'utilisateur) */}
          {subjects.filter(s => !s.is_default).map((subject) =>
            editingId === subject.id ? (
              <EditRow
                key={subject.id}
                subject={subject}
                onSave={(name, color, icon) => handleSaveEdit(subject.id, name, color, icon)}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <SubjectRow
                key={subject.id}
                subject={subject}
                onEdit={() => { setEditingId(subject.id); setShowAddForm(false) }}
                onDelete={() => handleDelete(subject.id)}
              />
            )
          )}

          {/* État vide (si aucune matière utilisateur) */}
          {subjects.filter(s => !s.is_default).length === 0 && !showAddForm && (
            <div className="text-center py-8 text-gray-400">
              <BookOpen size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">Aucune matière configurée.</p>
              <button
                onClick={() => setShowAddForm(true)}
                className="text-primary-600 text-sm mt-1 hover:underline"
              >
                Ajouter une matière
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
