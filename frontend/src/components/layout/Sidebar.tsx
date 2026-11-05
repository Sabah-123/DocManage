import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, MessageSquare, FolderOpen,
  Upload, User, LogOut, BookOpen, Clock
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { chatApi, ChatSession } from '@/lib/api'
import clsx from 'clsx'
import { isToday, isYesterday, isThisWeek, isThisMonth } from 'date-fns'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Tableau de bord' },
  { to: '/chat',      icon: MessageSquare,   label: 'Chat / Q&A' },
  { to: '/documents', icon: FolderOpen,      label: 'Mes documents' },
  { to: '/upload',    icon: Upload,          label: 'Uploader' },
  { to: '/profile',   icon: User,            label: 'Profil' },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<ChatSession[]>([])

  const fetchSessions = async () => {
    try {
      const res = await chatApi.getSessions()
      setSessions(res.data)
    } catch (e) {
      console.error("Failed to fetch sessions")
    }
  }

  useEffect(() => {
    fetchSessions()
    
    window.addEventListener('chatSessionCreated', fetchSessions)
    return () => window.removeEventListener('chatSessionCreated', fetchSessions)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const groupSessions = (sessions: ChatSession[]) => {
    const groups: Record<string, ChatSession[]> = {
      "Aujourd'hui": [],
      "Hier": [],
      "7 jours précédents": [],
      "Mois précédent": [],
      "Anciennes": []
    }

    sessions.forEach(session => {
      const date = new Date(session.updated_at || session.created_at)
      if (isToday(date)) groups["Aujourd'hui"].push(session)
      else if (isYesterday(date)) groups["Hier"].push(session)
      else if (isThisWeek(date)) groups["7 jours précédents"].push(session)
      else if (isThisMonth(date)) groups["Mois précédent"].push(session)
      else groups["Anciennes"].push(session)
    })

    return groups
  }

  const groupedSessions = groupSessions(sessions)

  return (
    <aside className="w-60 h-screen bg-white border-r border-gray-100 flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
            <BookOpen size={16} className="text-white" />
          </div>
          <div>
            <p className="font-semibold text-sm text-gray-900">DocManager</p>
            <p className="text-xs text-gray-400">Agentic AI</p>
          </div>
        </div>
      </div>

      {/* Navigation Principale */}
      <div className="px-3 py-4 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </div>

      {/* Historique des discussions */}
      <div className="flex-1 px-3 py-2 overflow-y-auto custom-scrollbar">
        <div className="px-3 mb-2 flex items-center gap-1.5 text-gray-400">
           <Clock size={12} />
           <p className="text-[10px] font-bold uppercase tracking-widest">Historique discussions</p>
        </div>
        
        <div className="space-y-4">
          {Object.entries(groupedSessions).map(([groupName, groupSessions]) => {
            if (groupSessions.length === 0) return null
            return (
              <div key={groupName} className="space-y-1">
                <div className="px-3 py-1">
                  <span className="text-[11px] font-semibold text-gray-400">{groupName}</span>
                </div>
                <div className="space-y-0.5">
                  {groupSessions.map(session => (
                    <NavLink
                      key={session.id}
                      to={`/chat?session=${session.id}`}
                      className={({ isActive }) =>
                        clsx(
                          'flex items-center gap-2.5 px-3 py-1.5 rounded-md text-[13px] transition-colors',
                          isActive
                            ? 'text-primary-700 bg-primary-50/50 font-medium'
                            : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'
                        )
                      }
                    >
                      <MessageSquare size={13} className="shrink-0 opacity-70" />
                      <span className="truncate">{session.title}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            )
          })}
          
          {sessions.length === 0 && (
            <div className="px-3 py-4 text-center">
              <p className="text-[11px] text-gray-400 italic">Aucune discussion</p>
            </div>
          )}
        </div>
      </div>

      {/* User + Logout */}
      <div className="px-3 py-4 border-t border-gray-100">
        <div className="flex items-center gap-3 px-3 py-2 mb-1">
          <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 text-xs font-semibold">
            {user?.username[0].toUpperCase()}
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500
                     hover:bg-red-50 hover:text-red-600 transition-colors font-medium"
        >
          <LogOut size={17} />
          Déconnexion
        </button>
      </div>
    </aside>
  )
}
