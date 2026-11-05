import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { FileText, MessageSquare, Upload, TrendingUp, Loader2 } from 'lucide-react'
import { dashboardApi, DashboardStats, Document } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'

const COLORS = ['#4f46e5', '#7c3aed', '#2563eb', '#0891b2', '#059669', '#d97706', '#dc2626']

function StatCard({ icon: Icon, label, value, color }: {
  icon: any; label: string; value: number | string; color: string
}) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    dashboardApi.stats()
      .then((r) => setStats(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={28} className="text-gray-300 animate-spin" />
      </div>
    )
  }

  if (!stats) return null

  const subjectData = Object.entries(stats.documents_by_subject).map(([name, value]) => ({
    name, value
  }))

  const typeData = Object.entries(stats.documents_by_type).map(([name, value]) => ({
    name, value
  }))

  return (
    <div className="p-8">
      {/* En-tête */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">
          Bonjour, {user?.username} 👋
        </h1>
        <p className="text-gray-500 text-sm mt-1">Voici un aperçu de votre espace documentaire</p>
      </div>

      {/* Cartes stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={FileText}     label="Documents indexés"  value={stats.total_documents}     color="bg-primary-600" />
        <StatCard icon={MessageSquare} label="Conversations"     value={stats.total_conversations} color="bg-purple-500"  />
        <StatCard icon={TrendingUp}   label="Matières couvertes" value={Object.keys(stats.documents_by_subject).length} color="bg-teal-500" />
        <StatCard icon={Upload}       label="Types de documents" value={Object.keys(stats.documents_by_type).length}    color="bg-orange-500" />
      </div>

      {/* Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Bar chart par matière */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-5">Documents par matière</h2>
          {subjectData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={subjectData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                />
                <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gray-300 text-sm">
              Aucune donnée
            </div>
          )}
        </div>

        {/* Pie chart par type */}
        <div className="card p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-5">Répartition par type</h2>
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={typeData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                  labelLine={false}
                >
                  {typeData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gray-300 text-sm">
              Aucune donnée
            </div>
          )}
        </div>
      </div>

      {/* Activité récente */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-800">Activité récente</h2>
          <button onClick={() => navigate('/documents')} className="text-sm text-primary-600 hover:underline">
            Voir tout
          </button>
        </div>
        {stats.recent_activity.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-400 text-sm">Aucun document récent</p>
            <button onClick={() => navigate('/upload')} className="btn-primary mt-3 text-sm">
              Uploader un document
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {stats.recent_activity.map((doc: Document) => (
              <div key={doc.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <FileText size={15} className="text-gray-300 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {doc.title_suggested || doc.original_name}
                  </p>
                  <p className="text-xs text-gray-400">
                    {doc.subject || '—'} · {doc.doc_type || '—'} ·{' '}
                    {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                  </p>
                </div>
                <span className={`badge text-xs ${
                  doc.status === 'ready'
                    ? 'bg-green-100 text-green-700'
                    : doc.status === 'error'
                    ? 'bg-red-100 text-red-600'
                    : 'bg-gray-100 text-gray-500'
                }`}>
                  {doc.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
