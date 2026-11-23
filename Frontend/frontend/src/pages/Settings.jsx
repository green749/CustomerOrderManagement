import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Settings as SettingsIcon,
  User,
  Shield,
  Mail,
  Server,
  Layers,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Sliders,
  Users,
  Plus,
  Edit2,
  UserX,
  UserCheck,
  Save,
  X,
  Lock,
  ArrowRight,
  Database,
  Building2,
  Check,
  Send,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../api/auth.api'
import { agentsApi } from '../api/agents.api'
import { isAdmin, canManageApprovals } from '../utils/permissions'

const DEPARTMENTS = ['ERP', 'MMS', 'MES', 'WMS', 'QMS', 'TMS', 'PLM']

export default function Settings() {
  const { user } = useAuth()
  const userIsAdmin = isAdmin(user)

  const [activeTab, setActiveTab] = useState('profile')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  // Modals / forms
  const [showUserModal, setShowUserModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [userFormData, setUserFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'operational',
    department: 'MMS',
    can_approve_commitments: false,
  })

  // Contact editing
  const [editingContact, setEditingContact] = useState(null)
  const [contactEmailInput, setContactEmailInput] = useState('')

  // Mapping editing
  const [editingMapping, setEditingMapping] = useState(null)
  const [mappingDeptInput, setMappingDeptInput] = useState('ERP')

  const [testingContactEmail, setTestingContactEmail] = useState(null)
  const [smtpConfig, setSmtpConfig] = useState({
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    smtp_from: '',
    is_configured: false,
  })

  const {
    data: allSettingsData = { contacts: [], mappings: [], users: [], smtp: null },
    isLoading: loading,
    refetch: loadAllData,
  } = useQuery({
    queryKey: ['settings-data', userIsAdmin],
    queryFn: async () => {
      const promises = [
        authApi.listDepartmentContacts().catch(() => []),
        authApi.listDepartmentMappings().catch(() => []),
      ]
      if (userIsAdmin) {
        promises.push(authApi.listUsers().catch(() => []))
        promises.push(agentsApi.getSmtpConfig().catch(() => null))
      }
      const [contactsRes, mappingsRes, usersRes, smtpRes] = await Promise.all(promises)
      return {
        contacts: Array.isArray(contactsRes) ? contactsRes : [],
        mappings: Array.isArray(mappingsRes) ? mappingsRes : [],
        users: Array.isArray(usersRes) ? usersRes : [],
        smtp: smtpRes || null,
      }
    },
    staleTime: 60 * 1000,
  })

  const contacts = allSettingsData.contacts
  const mappings = allSettingsData.mappings
  const users = allSettingsData.users

  useEffect(() => {
    if (allSettingsData.smtp) {
      setSmtpConfig({
        smtp_host: allSettingsData.smtp.smtp_host || '',
        smtp_port: allSettingsData.smtp.smtp_port || 587,
        smtp_user: allSettingsData.smtp.smtp_user || '',
        smtp_password: '',
        smtp_from: allSettingsData.smtp.smtp_from || '',
        is_configured: allSettingsData.smtp.is_configured || false,
      })
    }
  }, [allSettingsData.smtp])

  const handleTestEmail = async (email, dept) => {
    setTestingContactEmail(email)
    try {
      setNotice(`Sending verified test notification to ${email}...`)
      const res = await agentsApi.sendTestNotification({
        recipient_email: email,
        recipient_category: dept === 'CUSTOMER_SERVICE' ? 'CUSTOMER_SERVICE' : 'OPERATIONAL',
      })
      if (res.status === 'SENT') {
        setNotice(`Test email delivered successfully to ${email}!`)
      } else {
        setError(`Email recorded as ${res.status}: ${res.failure_reason || 'Inspect details in Monitoring Outbox.'}`)
      }
      setTimeout(() => { setNotice(''); setError('') }, 7000)
    } catch (err) {
      setError(`Test email failed: ${err.response?.data?.detail || err.message}`)
      setTimeout(() => setError(''), 6000)
    } finally {
      setTestingContactEmail(null)
    }
  }

  const handleSaveSmtp = async (e) => {
    e.preventDefault()
    setNotice('')
    setError('')
    try {
      await agentsApi.updateSmtpConfig(smtpConfig)
      setNotice('SMTP relay settings saved successfully! Outgoing emails will now route through your SMTP server.')
      const updated = await agentsApi.getSmtpConfig()
      setSmtpConfig((prev) => ({ ...prev, is_configured: updated.is_configured }))
      setTimeout(() => setNotice(''), 6000)
    } catch (err) {
      setError(`Failed to save SMTP configuration: ${err.response?.data?.detail || err.message}`)
    }
  }

  useEffect(() => {
    loadAllData()
  }, [userIsAdmin])

  const handleOpenCreateUser = () => {
    setEditingUser(null)
    setUserFormData({
      email: '',
      full_name: '',
      password: '',
      role: 'operational',
      department: 'MMS',
      can_approve_commitments: false,
    })
    setShowUserModal(true)
  }

  const handleOpenEditUser = (u) => {
    setEditingUser(u)
    setUserFormData({
      email: u.email,
      full_name: u.full_name,
      password: '',
      role: u.role || 'operational',
      department: u.department || 'MMS',
      can_approve_commitments: Boolean(u.can_approve_commitments),
    })
    setShowUserModal(true)
  }

  const handleSaveUser = async (e) => {
    e.preventDefault()
    setNotice('')
    setError('')
    try {
      if (editingUser) {
        await authApi.updateUser(editingUser.id, {
          full_name: userFormData.full_name,
          role: userFormData.role,
          department: userFormData.role === 'operational' ? userFormData.department : null,
          can_approve_commitments: userFormData.can_approve_commitments,
          password: userFormData.password || undefined,
        })
        setNotice(`User '${editingUser.email}' updated successfully.`)
      } else {
        await authApi.createUser({
          email: userFormData.email,
          full_name: userFormData.full_name,
          password: userFormData.password,
          role: userFormData.role,
          department: userFormData.role === 'operational' ? userFormData.department : null,
          can_approve_commitments: userFormData.can_approve_commitments,
        })
        setNotice(`New user '${userFormData.email}' created successfully.`)
      }
      setShowUserModal(false)
      loadAllData()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to save user.')
    }
  }

  const handleToggleUserActive = async (u) => {
    try {
      await authApi.updateUser(u.id, { is_active: !u.is_active })
      setNotice(`User '${u.email}' status changed to ${!u.is_active ? 'ACTIVE' : 'INACTIVE'}.`)
      loadAllData()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update user status.')
    }
  }

  const handleSaveContact = async (contact) => {
    try {
      await authApi.updateDepartmentContact({
        department: contact.department,
        role_name: contact.role_name,
        email: contactEmailInput.trim().toLowerCase(),
        is_active: contact.is_active,
      })
      setEditingContact(null)
      setNotice(`Notification recipient for ${contact.department} updated.`)
      loadAllData()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update contact.')
    }
  }

  const handleSaveMapping = async (m) => {
    try {
      await authApi.updateDepartmentMapping(m.id, {
        issue_category: m.issue_category,
        issue_label: m.issue_label,
        responsible_department: mappingDeptInput,
        description: m.description,
        is_active: m.is_active,
      })
      setEditingMapping(null)
      setNotice(`Mapping for '${m.issue_label}' updated to ${mappingDeptInput}.`)
      loadAllData()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update mapping.')
    }
  }

  const userRole = (user?.role || 'OPERATIONAL').toUpperCase()

  return (
    <div className="page-stack">
      {notice && (
        <div style={{ padding: '12px 16px', background: 'rgba(34, 197, 94, 0.12)', border: '1px solid #22c55e', borderRadius: 8, color: '#16a34a', fontSize: 13, display: 'flex', alignItems: 'center', gap: 10 }}>
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div style={{ padding: '12px 16px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444', borderRadius: 8, color: '#dc2626', fontSize: 13, display: 'flex', alignItems: 'center', gap: 10 }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* NAVIGATION TABS */}
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--mfg-border-default)', paddingBottom: 12 }}>
        <button
          type="button"
          onClick={() => setActiveTab('profile')}
          className={`button ${activeTab === 'profile' ? 'button-primary' : 'button-secondary'}`}
          style={{ fontSize: 12 }}
        >
          <User size={14} /> My Profile &amp; Permissions
        </button>

        {userIsAdmin && (
          <>
            <button
              type="button"
              onClick={() => setActiveTab('users')}
              className={`button ${activeTab === 'users' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 12 }}
            >
              <Users size={14} /> User Management &amp; RBAC ({users.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('contacts')}
              className={`button ${activeTab === 'contacts' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 12 }}
            >
              <Mail size={14} /> Notification Recipients ({contacts.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('mappings')}
              className={`button ${activeTab === 'mappings' ? 'button-primary' : 'button-secondary'}`}
              style={{ fontSize: 12 }}
            >
              <Building2 size={14} /> Department Mappings ({mappings.length})
            </button>
          </>
        )}

        <button
          type="button"
          onClick={() => setActiveTab('system')}
          className={`button ${activeTab === 'system' ? 'button-primary' : 'button-secondary'}`}
          style={{ fontSize: 12 }}
        >
          <Server size={14} /> Infrastructure &amp; Agents
        </button>
      </div>

      {/* TAB 1: PROFILE & ACTIVE PERMISSIONS */}
      {activeTab === 'profile' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: 20 }}>
          <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 18 }}>
              <div style={{ width: 50, height: 50, borderRadius: 12, background: 'linear-gradient(135deg, var(--mfg-accent-primary), #6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 20, fontWeight: 700 }}>
                {user?.full_name?.[0] || 'U'}
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>{user?.full_name}</div>
                <div style={{ fontSize: 12, color: 'var(--mfg-text-secondary)' }}>{user?.email}</div>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <span className="mfg-badge mfg-badge-ready" style={{ fontSize: 12 }}>{userRole}</span>
              </div>
            </div>

            <div style={{ background: 'var(--mfg-bg-surface)', borderRadius: 8, padding: 14, border: '1px solid var(--mfg-border-subtle)', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--mfg-text-muted)' }}>Assigned Department:</span>
                <span style={{ fontWeight: 600, color: 'var(--mfg-text-primary)' }}>{user?.department || 'Cross-Department / Enterprise'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--mfg-text-muted)' }}>Commercial Approval Authority:</span>
                <span style={{ color: canManageApprovals(user) ? '#22C55E' : '#F59E0B', fontWeight: 600 }}>
                  {canManageApprovals(user) ? 'Authorized Commercial Sign-off' : 'Read-Only (No Approval Permission)'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--mfg-text-muted)' }}>Account Status:</span>
                <span style={{ color: user?.is_active ? '#22C55E' : '#EF4444', fontWeight: 600 }}>
                  {user?.is_active ? 'Active & Authenticated' : 'Deactivated'}
                </span>
              </div>
            </div>
          </div>

          <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--mfg-text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={18} style={{ color: 'var(--mfg-accent-primary)' }} />
              Active Granted Permissions
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(user?.permissions || ['order:view', 'monitoring:view']).map((perm) => (
                <span key={perm} style={{ padding: '4px 10px', background: 'rgba(111, 61, 186, 0.1)', border: '1px solid rgba(111, 61, 186, 0.25)', borderRadius: 6, fontSize: 11, fontFamily: 'monospace', color: 'var(--brand-purple)' }}>
                  {perm}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: USER MANAGEMENT (ADMIN ONLY) */}
      {activeTab === 'users' && userIsAdmin && (
        <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>Application Users &amp; Role Assignments</div>
              <div style={{ fontSize: 12, color: 'var(--mfg-text-secondary)' }}>
                Configure user roles (Administrator, Customer Service, Operational), department assignments, and explicit commercial approval permissions.
              </div>
            </div>
            <button type="button" className="button button-primary" onClick={handleOpenCreateUser} style={{ fontSize: 12 }}>
              <Plus size={14} /> Create User
            </button>
          </div>

          <div className="table-scroll" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', border: 'none', borderRadius: 0, scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--mfg-border-default)', color: 'var(--mfg-text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: 10 }}>User</th>
                  <th style={{ padding: 10 }}>Role</th>
                  <th style={{ padding: 10 }}>Department</th>
                  <th style={{ padding: 10 }}>Approval Authority</th>
                  <th style={{ padding: 10 }}>Status</th>
                  <th style={{ padding: 10, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--mfg-border-subtle)' }}>
                    <td style={{ padding: 10 }}>
                      <div style={{ fontWeight: 600, color: 'var(--mfg-text-primary)' }}>{u.full_name}</div>
                      <div style={{ color: 'var(--mfg-text-muted)', fontSize: 11 }}>{u.email}</div>
                    </td>
                    <td style={{ padding: 10 }}>
                      <span className="mfg-badge" style={{ textTransform: 'uppercase', fontSize: 11 }}>
                        {u.role}
                      </span>
                    </td>
                    <td style={{ padding: 10, color: 'var(--mfg-text-primary)' }}>
                      {u.department || '—'}
                    </td>
                    <td style={{ padding: 10 }}>
                      {u.can_approve_commitments || u.role === 'admin' ? (
                        <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
                          <Check size={14} /> Authorized Approver
                        </span>
                      ) : (
                        <span style={{ color: 'var(--mfg-text-muted)' }}>No Approval Authority</span>
                      )}
                    </td>
                    <td style={{ padding: 10 }}>
                      <span style={{ color: u.is_active ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={{ padding: 10, textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: 6 }}>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => handleOpenEditUser(u)}
                          style={{ padding: '4px 8px', fontSize: 11 }}
                        >
                          <Edit2 size={12} /> Edit
                        </button>
                        {u.id !== user?.id && (
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => handleToggleUserActive(u)}
                            style={{ padding: '4px 8px', fontSize: 11, color: u.is_active ? '#ef4444' : '#22c55e' }}
                          >
                            {u.is_active ? <UserX size={12} /> : <UserCheck size={12} />}
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: NOTIFICATION RECIPIENTS (ADMIN ONLY) */}
      {activeTab === 'contacts' && userIsAdmin && (
        <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>Department &amp; Customer Service Notification Recipients</div>
            <div style={{ fontSize: 12, color: 'var(--mfg-text-secondary)' }}>
              Agent 3 independently dispatches operational corrective action notices to departments and delivery risk alerts to Customer Service.
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
            {contacts.map((c) => {
              const isEditing = editingContact?.id === c.id
              return (
                <div key={c.id || c.department} style={{ background: 'var(--mfg-bg-surface)', border: '1px solid var(--mfg-border-subtle)', borderRadius: 8, padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--mfg-accent-primary)' }}>
                      {c.department}
                    </span>
                    <span className="mfg-badge mfg-badge-ready" style={{ fontSize: 10 }}>{c.is_active ? 'ACTIVE' : 'DISABLED'}</span>
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--mfg-text-primary)', marginBottom: 6 }}>{c.role_name}</div>

                  {isEditing ? (
                    <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                      <input
                        type="email"
                        value={contactEmailInput}
                        onChange={(e) => setContactEmailInput(e.target.value)}
                        style={{ flex: 1, padding: '6px 8px', borderRadius: 6, border: '1px solid var(--mfg-border-default)', background: 'var(--mfg-bg-card)', color: 'var(--mfg-text-primary)', fontSize: 11 }}
                      />
                      <button type="button" className="button button-primary" onClick={() => handleSaveContact(c)} style={{ padding: '6px 10px', fontSize: 11 }}>
                        <Save size={12} />
                      </button>
                      <button type="button" className="button button-secondary" onClick={() => setEditingContact(null)} style={{ padding: '6px 10px', fontSize: 11 }}>
                        <X size={12} />
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                      <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--mfg-text-secondary)' }}>{c.email}</span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => handleTestEmail(c.email, c.department)}
                          disabled={testingContactEmail === c.email}
                          style={{ padding: '4px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                          title="Send a verified test email to this address"
                        >
                          <Send size={11} /> {testingContactEmail === c.email ? 'Sending…' : 'Test'}
                        </button>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => {
                            setEditingContact(c)
                            setContactEmailInput(c.email)
                          }}
                          style={{ padding: '4px 8px', fontSize: 11 }}
                        >
                          <Edit2 size={12} /> Edit
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* TAB 4: DEPARTMENT MAPPINGS (ADMIN ONLY) */}
      {activeTab === 'mappings' && userIsAdmin && (
        <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--mfg-text-primary)' }}>Issue Category to Department Responsibility Mappings</div>
            <div style={{ fontSize: 12, color: 'var(--mfg-text-secondary)' }}>
              Configurable mappings routing identified operational exceptions to responsible plant departments.
            </div>
          </div>

          <div className="table-scroll" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', border: 'none', borderRadius: 0, scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--mfg-border-default)', color: 'var(--mfg-text-muted)', textAlign: 'left' }}>
                <th style={{ padding: 10 }}>Issue Category</th>
                <th style={{ padding: 10 }}>Description &amp; Context</th>
                <th style={{ padding: 10 }}>Responsible Department</th>
                <th style={{ padding: 10, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((m) => {
                const isEditing = editingMapping?.id === m.id
                return (
                  <tr key={m.id} style={{ borderBottom: '1px solid var(--mfg-border-subtle)' }}>
                    <td style={{ padding: 10, fontWeight: 600, color: 'var(--mfg-text-primary)' }}>
                      {m.issue_label}
                      <div style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--mfg-text-muted)' }}>{m.issue_category}</div>
                    </td>
                    <td style={{ padding: 10, color: 'var(--mfg-text-secondary)' }}>{m.description}</td>
                    <td style={{ padding: 10 }}>
                      {isEditing ? (
                        <select
                          value={mappingDeptInput}
                          onChange={(e) => setMappingDeptInput(e.target.value)}
                          style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--mfg-border-default)', background: 'var(--mfg-bg-card)', color: 'var(--mfg-text-primary)', fontSize: 12 }}
                        >
                          {DEPARTMENTS.map((d) => (
                            <option key={d} value={d}>{d}</option>
                          ))}
                        </select>
                      ) : (
                        <span className="mfg-badge" style={{ fontWeight: 700 }}>{m.responsible_department}</span>
                      )}
                    </td>
                    <td style={{ padding: 10, textAlign: 'right' }}>
                      {isEditing ? (
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button type="button" className="button button-primary" onClick={() => handleSaveMapping(m)} style={{ padding: '4px 8px', fontSize: 11 }}>
                            <Save size={12} /> Save
                          </button>
                          <button type="button" className="button button-secondary" onClick={() => setEditingMapping(null)} style={{ padding: '4px 8px', fontSize: 11 }}>
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => {
                            setEditingMapping(m)
                            setMappingDeptInput(m.responsible_department)
                          }}
                          style={{ padding: '4px 8px', fontSize: 11 }}
                        >
                          <Edit2 size={12} /> Reassign
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* TAB 5: SYSTEM INFRASTRUCTURE */}
      {activeTab === 'system' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: 20 }}>
          <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--mfg-text-primary)', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <Server size={18} style={{ color: 'var(--mfg-accent-primary)' }} />
              Three-Agent Infrastructure Architecture
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, background: 'var(--mfg-bg-surface)', borderRadius: 8 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--mfg-text-primary)' }}>Agent 1 – Order Management Intelligence</div>
                  <div style={{ fontSize: 11, color: 'var(--mfg-text-secondary)' }}>Conversational inquiry with ReAct loop &amp; domain tools</div>
                </div>
                <span className="mfg-badge mfg-badge-ready">ONLINE</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, background: 'var(--mfg-bg-surface)', borderRadius: 8 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--mfg-text-primary)' }}>Agent 2 – Feasibility &amp; Commitment Engine</div>
                  <div style={{ fontSize: 11, color: 'var(--mfg-text-secondary)' }}>Autonomous 7-department readiness assessment &amp; proposal submission</div>
                </div>
                <span className="mfg-badge mfg-badge-ready">ONLINE</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 12, background: 'var(--mfg-bg-surface)', borderRadius: 8 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--mfg-text-primary)' }}>Agent 3 – Surveillance &amp; Email Dispatcher</div>
                  <div style={{ fontSize: 11, color: 'var(--mfg-text-secondary)' }}>Daily scheduler with distributed DB lease &amp; independent CS notifications</div>
                </div>
                <span className="mfg-badge mfg-badge-ready">ACTIVE</span>
              </div>
            </div>
          </div>

          <div className="card" style={{ background: 'var(--mfg-bg-card)', border: '1px solid var(--mfg-border-default)', borderRadius: 12, padding: 24 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--mfg-text-primary)', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <Mail size={18} style={{ color: 'var(--mfg-accent-primary)' }} />
              Email Notification Provider &amp; SMTP Relay
            </div>

            <form onSubmit={handleSaveSmtp} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10 }}>
                <div>
                  <label className="input-label" style={{ fontSize: 11 }}>SMTP Host</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. smtp.gmail.com"
                    value={smtpConfig.smtp_host}
                    onChange={(e) => setSmtpConfig({ ...smtpConfig, smtp_host: e.target.value })}
                    style={{ fontSize: 12 }}
                  />
                </div>
                <div>
                  <label className="input-label" style={{ fontSize: 11 }}>Port</label>
                  <input
                    type="number"
                    className="input"
                    placeholder="587"
                    value={smtpConfig.smtp_port}
                    onChange={(e) => setSmtpConfig({ ...smtpConfig, smtp_port: parseInt(e.target.value) || 587 })}
                    style={{ fontSize: 12 }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label className="input-label" style={{ fontSize: 11 }}>SMTP Username</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. user@gmail.com"
                    value={smtpConfig.smtp_user}
                    onChange={(e) => setSmtpConfig({ ...smtpConfig, smtp_user: e.target.value })}
                    style={{ fontSize: 12 }}
                  />
                </div>
                <div>
                  <label className="input-label" style={{ fontSize: 11 }}>Password / App Password</label>
                  <input
                    type="password"
                    className="input"
                    placeholder={smtpConfig.is_configured ? '•••••••• (configured)' : 'App password'}
                    value={smtpConfig.smtp_password}
                    onChange={(e) => setSmtpConfig({ ...smtpConfig, smtp_password: e.target.value })}
                    style={{ fontSize: 12 }}
                  />
                </div>
              </div>

              <div>
                <label className="input-label" style={{ fontSize: 11 }}>From Email Address</label>
                <input
                  type="email"
                  className="input"
                  placeholder="e.g. notifications@manufacturing.com"
                  value={smtpConfig.smtp_from}
                  onChange={(e) => setSmtpConfig({ ...smtpConfig, smtp_from: e.target.value })}
                  style={{ fontSize: 12 }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                <span style={{ fontSize: 11, color: smtpConfig.is_configured ? '#16a34a' : 'var(--mfg-text-muted)', fontWeight: 600 }}>
                  {smtpConfig.is_configured ? '● SMTP Relay Configured' : '○ Not Configured (YOPmail fallback active)'}
                </span>
                <button type="submit" className="button button-primary" style={{ padding: '6px 14px', fontSize: 12 }}>
                  <Save size={13} /> Save SMTP Settings
                </button>
              </div>
            </form>

            <div style={{ background: 'var(--mfg-bg-surface)', borderRadius: 8, padding: 14, border: '1px solid var(--mfg-border-subtle)', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11 }}>
              <div style={{ color: 'var(--mfg-text-secondary)', lineHeight: 1.45 }}>
                <strong>Tip for Testing:</strong> For zero-credential test delivery, set recipient to any <code>@yopmail.com</code> address (e.g. <code>qa-alerts@yopmail.com</code>) — it delivers directly to <a href="https://yopmail.com" target="_blank" rel="noreferrer" style={{ color: 'var(--brand-purple)' }}>yopmail.com</a> without any SMTP server. For real Gmail, enter <code>smtp.gmail.com</code> with your Google App Password.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE / EDIT USER MODAL */}
      {showUserModal && (
        <div className="mfg-modal-overlay" role="dialog" aria-modal="true">
          <div className="mfg-modal-content" style={{ maxWidth: 520 }}>
            <div className="mfg-modal-header">
              <h2>
                <Users size={18} color="var(--brand-orange)" />
                {editingUser ? `Edit User: ${editingUser.email}` : 'Create New Application User'}
              </h2>
              <button type="button" className="icon-button" onClick={() => setShowUserModal(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveUser}>
              <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label className="input-label" htmlFor="user-fullname">Full Name</label>
                  <input
                    id="user-fullname"
                    className="input"
                    type="text"
                    required
                    value={userFormData.full_name}
                    onChange={(e) => setUserFormData({ ...userFormData, full_name: e.target.value })}
                  />
                </div>

                {!editingUser && (
                  <div>
                    <label className="input-label" htmlFor="user-email">Email Address</label>
                    <input
                      id="user-email"
                      className="input"
                      type="email"
                      required
                      value={userFormData.email}
                      onChange={(e) => setUserFormData({ ...userFormData, email: e.target.value })}
                    />
                  </div>
                )}

                <div>
                  <label className="input-label" htmlFor="user-pass">
                    {editingUser ? 'Reset Password (optional)' : 'Password'}
                  </label>
                  <input
                    id="user-pass"
                    className="input"
                    type="password"
                    placeholder={editingUser ? 'Leave blank to retain current' : 'Min 6 characters'}
                    required={!editingUser}
                    value={userFormData.password}
                    onChange={(e) => setUserFormData({ ...userFormData, password: e.target.value })}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label className="input-label" htmlFor="user-role">Role</label>
                    <select
                      id="user-role"
                      className="input select"
                      value={userFormData.role}
                      onChange={(e) => setUserFormData({ ...userFormData, role: e.target.value })}
                    >
                      <option value="operational">Operational</option>
                      <option value="customer_service">Customer Service</option>
                      <option value="admin">Administrator</option>
                    </select>
                  </div>

                  <div>
                    <label className="input-label" htmlFor="user-dept">Department</label>
                    <select
                      id="user-dept"
                      className="input select"
                      disabled={userFormData.role !== 'operational'}
                      value={userFormData.department}
                      onChange={(e) => setUserFormData({ ...userFormData, department: e.target.value })}
                    >
                      {DEPARTMENTS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div style={{ padding: 12, background: 'var(--mfg-bg-surface)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <input
                    type="checkbox"
                    id="approve-check"
                    checked={userFormData.can_approve_commitments}
                    onChange={(e) => setUserFormData({ ...userFormData, can_approve_commitments: e.target.checked })}
                    style={{ width: 16, height: 16, cursor: 'pointer' }}
                  />
                  <label htmlFor="approve-check" style={{ fontSize: 12, color: 'var(--mfg-text-primary)', cursor: 'pointer' }}>
                    Grant Commercial Commitment Approval Authority
                  </label>
                </div>
              </div>

              <div className="mfg-modal-footer">
                <button type="button" className="button button-secondary" onClick={() => setShowUserModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="button button-primary">
                  <Save size={14} /> Save User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
