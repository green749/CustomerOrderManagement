import { useState } from 'react'
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, Sparkles } from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getErrorMessage } from '../utils/format'
import { Input } from '../components/common/Input'
import { Button } from '../components/common/Button'
import gwcIcon from '../assets/gwc-icon.png'

export default function Login() {
  const { user, login, sessionNotice } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [validation, setValidation] = useState({})

  if (user) return <Navigate to="/" replace />

  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextValidation = {}
    if (!email.trim()) nextValidation.email = 'Enter your work email.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) nextValidation.email = 'Enter a valid email address.'
    if (!password) nextValidation.password = 'Enter your password.'
    setValidation(nextValidation)
    setError('')
    if (Object.keys(nextValidation).length) return
    setLoading(true)
    try {
      await login({ email: email.trim(), password })
      const destination = location.state?.from?.pathname ?? '/'
      navigate(destination, { replace: true })
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Unable to sign in. Please check your credentials.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <Link className="login-brand" to="/login" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src={gwcIcon} alt="GWC DATA.AI" style={{ width: 34, height: 34, objectFit: 'contain', filter: 'drop-shadow(0 2px 6px rgba(111, 61, 186, 0.4))' }} />
          <strong>Manufacturing 360</strong>
        </Link>
        <div className="login-story-content">
          <div className="story-tag"><Sparkles size={14} /> THREE-AGENT ORDER OPERATIONS</div>
          <h1>Every order has a story.<br /><em>See the whole picture.</em></h1>
          <p>End-to-end customer order feasibility, approval, and risk monitoring across all enterprise systems.</p>
          <div className="login-story-card">
            <div className="story-card-top"><span className="story-card-label">TODAY’S SNAPSHOT</span><span className="story-live"><i /> LIVE AGENTS</span></div>
            <div className="story-card-stat">Automated <strong>order orchestration.</strong></div>
            <div className="story-card-chart"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
            <div className="story-card-footer"><span>Multi-agent intelligence, zero order delays</span><span>✳</span></div>
          </div>
        </div>
        <div className="login-story-foot"><span>Intelligent Manufacturing Operations</span><span>© 2026 Manufacturing 360</span></div>
        <div className="login-decoration login-decoration-one" /><div className="login-decoration login-decoration-two" />
      </section>
      <section className="login-form-side">
        <div className="login-form-wrap">
          <div className="login-mobile-brand" style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center', marginBottom: 20 }}>
            <img src={gwcIcon} alt="GWC DATA.AI" style={{ width: 34, height: 34, objectFit: 'contain' }} />
            <strong>Manufacturing 360</strong>
          </div>
          <div className="login-form-heading"><span className="login-icon"><LockKeyhole size={19} /></span><h2>Welcome back</h2><p>Sign in to your operations workspace.</p></div>
          {sessionNotice && <div className="login-session-notice" role="status">{sessionNotice}</div>}
          <form onSubmit={handleSubmit} noValidate>
            <label className={`login-field${validation.email ? ' field-invalid' : ''}`}><span>Work email</span><div className="login-input-wrap"><Mail size={17} /><Input bare type="email" autoComplete="email" value={email} onChange={(event) => { setEmail(event.target.value); setValidation((current) => ({ ...current, email: '' })) }} placeholder="you@company.com" aria-invalid={Boolean(validation.email)} /></div>{validation.email && <small>{validation.email}</small>}</label>
            <label className={`login-field${validation.password ? ' field-invalid' : ''}`}><span>Password</span><div className="login-input-wrap"><LockKeyhole size={17} /><Input bare type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => { setPassword(event.target.value); setValidation((current) => ({ ...current, password: '' })) }} placeholder="Enter your password" aria-invalid={Boolean(validation.password)} /><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>{validation.password && <small>{validation.password}</small>}</label>
            {error && <div className="login-error" role="alert">{error}</div>}
            <Button type="submit" className="button-login" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'} {!loading && <ArrowRight size={17} />}</Button>
          </form>
          <div className="login-security"><LockKeyhole size={14} /> Secure access to your company workspace</div>
          <p className="login-no-account">Need access? Contact your workspace administrator.</p>
        </div>
      </section>
    </main>
  )
}
