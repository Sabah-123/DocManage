import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, LogOut, Shield } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import SubjectsManager from '@/components/SubjectsManager'

export default function ProfilePage() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [confirmed, setConfirmed] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900 mb-8">Profil</h1>

      {/* Info utilisateur */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-primary-100 flex items-center justify-center text-primary-700 text-2xl font-bold">
            {user?.username[0].toUpperCase()}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{user?.username}</h2>
          </div>
        </div>
      </div>

      

      {/* Matières */}
      <SubjectsManager />

      {/* Déconnexion */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-800 mb-4">Session</h3>
        {!confirmed ? (
          <button
            onClick={() => setConfirmed(true)}
            className="btn-danger flex items-center gap-2"
          >
            <LogOut size={16} />
            Se déconnecter
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <p className="text-sm text-gray-600">Confirmer la déconnexion ?</p>
            <button onClick={handleLogout} className="btn-danger text-sm px-3 py-1.5">Oui, déconnecter</button>
            <button onClick={() => setConfirmed(false)} className="btn-secondary text-sm px-3 py-1.5">Annuler</button>
          </div>
        )}
      </div>
    </div>
  )
}
