import { useState, useEffect, useRef } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

type Page = 'login' | 'dashboard' | 'chat' | 'agents' | 'scan'

interface Message {
  id: number
  role: string
  content: string
  model_tier: string
}

interface Conversation {
  id: number
  title: string
}

function App() {
  const [token, setToken] = useState<string>(localStorage.getItem('token') || '')
  const [page, setPage] = useState<Page>('chat')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [convId, setConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [convs, setConvs] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(false)
  const [scanUrl, setScanUrl] = useState('')
  const [scanResult, setScanResult] = useState<any>(null)
  const chatEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (token) {
      fetch(`${API}/conversations`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json())
        .then(setConvs)
        .catch(() => {})
    }
  }, [token])

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const login = async () => {
    try {
      const r = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!r.ok) { alert('Login failed'); return }
      const data = await r.json()
      setToken(data.access_token)
      localStorage.setItem('token', data.access_token)
    } catch (e: any) { alert('Connection error: ' + e.message) }
  }

  const register = async () => {
    try {
      const r = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name: email.split('@')[0], org_name: 'My Org' }),
      })
      if (!r.ok) { const d = await r.json(); alert(d.detail); return }
      const data = await r.json()
      setToken(data.access_token)
      localStorage.setItem('token', data.access_token)
    } catch (e: any) { alert('Connection error: ' + e.message) }
  }

  const sendMessage = async () => {
    if (!msg.trim()) return
    setLoading(true)
    const userMsg = msg
    setMsg('')
    try {
      const r = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: userMsg, conversation_id: convId }),
      })
      if (!r.ok) throw new Error('Chat failed')
      const data = await r.json()
      setConvId(data.conversation_id)
      setMessages(prev => [
        ...prev,
        { id: Date.now(), role: 'user', content: userMsg, model_tier: data.model_tier },
        { id: Date.now() + 1, role: 'assistant', content: data.response || '[No response]', model_tier: data.model_tier },
      ])
      // Refresh conversation list
      fetch(`${API}/conversations`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json()).then(setConvs).catch(() => {})
    } catch (e: any) { alert('Error: ' + e.message) }
    setLoading(false)
  }

  const loadConversation = async (id: number) => {
    setConvId(id)
    try {
      const r = await fetch(`${API}/conversations/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error('Failed')
      const data = await r.json()
      setMessages(data)
    } catch (e: any) { alert('Error: ' + e.message) }
  }

  const scanMCP = async () => {
    if (!scanUrl.trim()) return
    setScanResult(null)
    try {
      const r = await fetch(`${API}/scan-mcp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ url: scanUrl, timeout: 3.0 }),
      })
      if (!r.ok) throw new Error('Scan failed')
      const data = await r.json()
      setScanResult(data)
    } catch (e: any) { alert('Error: ' + e.message) }
  }

  if (!token) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '12px', width: '360px' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>TurinTech Platform</h1>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', fontSize: '0.875rem' }}>Enterprise AI Infrastructure</p>
          <input style={inputStyle} placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
          <input style={inputStyle} placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button style={{ ...btnStyle, flex: 1 }} onClick={login}>Sign In</button>
            <button style={{ ...btnStyle, flex: 1, background: 'var(--primary-dark)' }} onClick={register}>Register</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div style={{ width: '200px', background: 'var(--bg-card)', borderRight: '1px solid var(--border)', padding: '1rem' }}>
        <h2 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-muted)' }}>TURINTECH</h2>
        {(['chat', 'dashboard', 'agents', 'scan'] as Page[]).map(p => (
          <div key={p} onClick={() => setPage(p)}
            style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', cursor: 'pointer', marginBottom: '0.25rem',
              background: page === p ? 'var(--primary)' : 'transparent', fontWeight: page === p ? 600 : 400 }}>
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </div>
        ))}
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Conversations</h3>
          {convs.map(c => (
            <div key={c.id} onClick={() => loadConversation(c.id)}
              style={{ padding: '0.4rem 0.5rem', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '4px',
                background: convId === c.id ? 'var(--bg-input)' : 'transparent' }}>
              {c.title.substring(0, 30)}
            </div>
          ))}
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, padding: '1.5rem', overflow: 'auto' }}>
        {page === 'chat' && (
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <div style={{ background: 'var(--bg-card)', borderRadius: '12px', minHeight: '500px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, padding: '1rem', overflow: 'auto' }}>
                {messages.length === 0 && (
                  <div style={{ textAlign: 'center', marginTop: '4rem', color: 'var(--text-muted)' }}>
                    <p style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>Ask anything</p>
                    <p style={{ fontSize: '0.85rem' }}>Upload documents, analyze data, generate reports</p>
                  </div>
                )}
                {messages.map(m => (
                  <div key={m.id} style={{ marginBottom: '1rem', display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{ maxWidth: '70%', padding: '0.75rem 1rem', borderRadius: '12px',
                      background: m.role === 'user' ? 'var(--primary)' : 'var(--bg-input)',
                      fontSize: '0.9rem', lineHeight: '1.5' }}>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                        {m.model_tier && `via ${m.model_tier}`}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={chatEnd} />
              </div>
              <div style={{ borderTop: '1px solid var(--border)', padding: '1rem', display: 'flex', gap: '0.5rem' }}>
                <input style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
                  placeholder="Type a message..." value={msg}
                  onChange={e => setMsg(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMessage()} />
                <button style={btnStyle} onClick={sendMessage} disabled={loading}>
                  {loading ? '...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}

        {page === 'dashboard' && (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Dashboard</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
              {[
                { label: 'API Status', value: 'Online', color: 'var(--success)' },
                { label: 'Model Tier', value: 'T1-T4', color: 'var(--primary)' },
                { label: 'Conversations', value: convs.length.toString(), color: 'var(--warning)' },
                { label: 'Compliance', value: 'CMMC 2.0', color: 'var(--success)' },
              ].map(card => (
                <div key={card.label} style={{ background: 'var(--bg-card)', borderRadius: '8px', padding: '1.25rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{card.label}</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: card.color }}>{card.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {page === 'agents' && (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Agents</h2>
            <p style={{ color: 'var(--text-muted)' }}>Agent inventory and monitoring — deploy ACP separately for full agent governance.</p>
          </div>
        )}

        {page === 'scan' && (
          <div style={{ maxWidth: '600px' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>MCP Security Scanner</h2>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input style={{ ...inputStyle, flex: 1, marginBottom: 0 }} placeholder="MCP server URL (e.g. http://localhost:3001)"
                value={scanUrl} onChange={e => setScanUrl(e.target.value)} />
              <button style={btnStyle} onClick={scanMCP}>Scan</button>
            </div>
            {scanResult && (
              <div style={{ background: 'var(--bg-card)', borderRadius: '8px', padding: '1rem' }}>
                <div style={{ marginBottom: '0.5rem' }}>
                  Status: <strong>{scanResult.reachable ? 'Reachable' : 'Unreachable'}</strong>
                  {scanResult.requires_auth !== null && ` | Auth: ${scanResult.requires_auth ? 'Required' : 'Missing'}`}
                </div>
                {scanResult.findings?.map((f: any, i: number) => (
                  <div key={i} style={{ padding: '0.5rem', margin: '0.25rem 0', borderRadius: '4px',
                    background: f.severity === 'critical' ? '#7f1d1d' : f.severity === 'high' ? '#451a03' : 'var(--bg-input)',
                    fontSize: '0.85rem' }}>
                    <strong style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>{f.severity}</strong>: {f.description}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '0.65rem 0.75rem', borderRadius: '6px', border: '1px solid var(--border)',
  background: 'var(--bg-input)', color: 'var(--text)', fontSize: '0.9rem', marginBottom: '0.75rem', outline: 'none',
}

const btnStyle: React.CSSProperties = {
  padding: '0.65rem 1rem', borderRadius: '6px', border: 'none', background: 'var(--primary)',
  color: '#fff', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer',
}

export default App
