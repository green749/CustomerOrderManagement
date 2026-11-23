import { useState, useEffect, useRef } from 'react'
import {
  Bot,
  Send,
  X,
  Sparkles,
  RotateCcw,
  MessageSquare,
  AlertCircle,
  ChevronDown,
} from 'lucide-react'
import { agentApi } from '../../api/agent.api'
import { ToolTrace } from '../agent/ToolTrace'
import { useAuth } from '../../context/AuthContext'
import { getErrorMessage } from '../../utils/format'

const SUGGESTED_PROMPTS = [
  'Which orders are at risk of delay?',
  'Show me shipment status of recent orders',
  'Are there any quality inspection concerns?',
  'What is the inventory health status?',
]

export function cleanAssistantMessage(content) {
  if (!content || typeof content !== 'string') return ''
  let text = content.trim()

  // 1. Remove markdown fences if wrapped: ```json ... ``` or ``` ... ```
  if (text.startsWith('```')) {
    text = text.replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```$/, '').trim()
  }

  // 2. If it's a JSON string or contains thought/action/answer
  if ((text.startsWith('{') && text.endsWith('}')) || (text.includes('"thought"') && text.includes('"answer"'))) {
    try {
      const parsed = JSON.parse(text)
      if (parsed && typeof parsed === 'object') {
        const candidate = parsed.answer || parsed.response || parsed.final_answer || parsed.content
        if (candidate) return cleanAssistantMessage(candidate)
      }
    } catch {
      // Regex extraction for "answer" or "response"
      const m = text.match(/"(?:answer|response|final_answer)"\s*:\s*"((?:[^"\\]|\\.)*)"/s)
      if (m && m[1]) {
        try {
          return cleanAssistantMessage(JSON.parse(`"${m[1]}"`))
        } catch {
          return m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\t/g, '\t')
        }
      }
      // Greedier tail match if quote wasn't cleanly terminated
      const m2 = text.match(/"(?:answer|response|final_answer)"\s*:\s*"(.*)/s)
      if (m2 && m2[1]) {
        let tail = m2[1].replace(/"\s*\}?\s*$/, '')
        return tail.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\t/g, '\t')
      }
    }
  }

  return text
}

function renderFormattedInline(text) {
  if (!text) return null
  const parts = []
  let key = 0
  const pattern = /(\*\*.*?\*\*|`.*?`)/g
  let lastIndex = 0
  let match

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code
          key={key++}
          style={{
            background: 'rgba(0,0,0,0.06)',
            padding: '1px 5px',
            borderRadius: '4px',
            fontFamily: 'monospace',
            fontSize: '0.92em',
          }}
        >
          {token.slice(1, -1)}
        </code>
      )
    }
    lastIndex = pattern.lastIndex
  }
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }
  return parts.length ? parts : text
}

function FormattedContent({ content }) {
  const cleanText = cleanAssistantMessage(content)
  const lines = cleanText.split('\n')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {lines.map((line, idx) => {
        const trimmed = line.trim()
        if (!trimmed) {
          return <div key={idx} style={{ height: '3px' }} />
        }
        if (trimmed.startsWith('### ')) {
          return (
            <div key={idx} style={{ fontWeight: 700, fontSize: '13px', marginTop: '6px', color: '#1e293b' }}>
              {renderFormattedInline(trimmed.replace(/^###\s+/, ''))}
            </div>
          )
        }
        if (trimmed.startsWith('## ')) {
          return (
            <div key={idx} style={{ fontWeight: 800, fontSize: '13.5px', marginTop: '8px', color: '#0f172a' }}>
              {renderFormattedInline(trimmed.replace(/^##\s+/, ''))}
            </div>
          )
        }
        if (trimmed.startsWith('# ')) {
          return (
            <div key={idx} style={{ fontWeight: 800, fontSize: '14px', marginTop: '10px', color: '#0f172a' }}>
              {renderFormattedInline(trimmed.replace(/^#\s+/, ''))}
            </div>
          )
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={idx} style={{ display: 'flex', gap: '6px', paddingLeft: '4px', alignItems: 'flex-start' }}>
              <span style={{ color: '#ef4444', fontWeight: 700, lineHeight: 1.4 }}>•</span>
              <div style={{ flex: 1 }}>{renderFormattedInline(trimmed.replace(/^[-*]\s+/, ''))}</div>
            </div>
          )
        }
        return <div key={idx}>{renderFormattedInline(line)}</div>
      })}
    </div>
  )
}

function createMsgId(prefix) {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function FloatingChatbot() {
  const { user } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const requestCounterRef = useRef(0)

  // Scroll to bottom whenever messages or sending state changes
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, sending, isOpen])

  // Focus textarea when chat opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        textareaRef.current?.focus()
      }, 100)
    }
  }, [isOpen])

  const handleStartNewChat = () => {
    setConversationId(null)
    setMessages([])
    setSendError('')
    setInput('')
    requestCounterRef.current += 1
  }

  const handleSendMessage = async (textToSend) => {
    const text = (typeof textToSend === 'string' ? textToSend : input).trim()
    if (!text || sending) return

    const reqNum = ++requestCounterRef.current
    const pendingUserMsg = {
      id: createMsgId('user'),
      role: 'user',
      content: text,
      steps: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, pendingUserMsg])
    setInput('')
    setSending(true)
    setSendError('')

    try {
      const response = await agentApi.sendMessage(text, conversationId)
      if (requestCounterRef.current !== reqNum) return

      if (typeof response?.answer !== 'string') {
        throw new Error('Received invalid response from agent service.')
      }

      if (response.conversation_id) {
        setConversationId(response.conversation_id)
      }

      const assistantMsg = {
        id: response.message_id || createMsgId('asst'),
        role: 'assistant',
        content: response.answer,
        steps: Array.isArray(response.steps) ? response.steps : [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      if (requestCounterRef.current !== reqNum) return
      setSendError(getErrorMessage(err, 'Could not get response from AI Assistant.'))
      // Keep user message or restore text
    } finally {
      if (requestCounterRef.current === reqNum) {
        setSending(false)
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <>
      {/* Floating Chat Window */}
      {isOpen && (
        <aside
          role="dialog"
          aria-label="Order Management AI Chatbot"
          style={{
            position: 'fixed',
            bottom: '92px',
            right: '28px',
            width: '400px',
            maxWidth: 'calc(100vw - 36px)',
            height: '580px',
            maxHeight: 'calc(100vh - 120px)',
            background: 'var(--surface-hi, #ffffff)',
            borderRadius: '18px',
            boxShadow: '0 24px 50px -12px rgba(15, 23, 42, 0.28), 0 0 0 1px rgba(0, 0, 0, 0.08)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            zIndex: 99999,
            animation: 'fadeInUp 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Header */}
          <div
            style={{
              background: 'linear-gradient(135deg, #1e1b4b 0%, #31104b 60%, #450a0a 100%)',
              padding: '14px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 6px rgba(239, 68, 68, 0.4)',
                  flexShrink: 0,
                }}
              >
                <Bot size={20} color="#ffffff" />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '13px', letterSpacing: '-0.2px' }}>
                  Order Management Agent
                </div>
                <div
                  style={{
                    fontSize: '11px',
                    color: '#fca5a5',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                  }}
                >
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: '#22c55e',
                      boxShadow: '0 0 6px #22c55e',
                      display: 'inline-block',
                    }}
                  />
                  Agent 1 · Ready to assist
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                onClick={handleStartNewChat}
                disabled={sending}
                title="Start new conversation"
                style={{
                  background: 'rgba(255, 255, 255, 0.12)',
                  border: '1px solid rgba(255, 255, 255, 0.18)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  padding: '6px 8px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: sending ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'background 0.15s',
                }}
              >
                <RotateCcw size={13} />
                <span>New</span>
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Close chat"
                style={{
                  background: 'rgba(255, 255, 255, 0.12)',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#ffffff',
                  width: '28px',
                  height: '28px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages Body */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              background: 'var(--surface, #f8fafc)',
            }}
          >
            {messages.length === 0 && (
              <div
                style={{
                  margin: 'auto 0',
                  textAlign: 'center',
                  padding: '12px 6px',
                }}
              >
                <div
                  style={{
                    width: '46px',
                    height: '46px',
                    borderRadius: '50%',
                    background: 'rgba(239, 68, 68, 0.1)',
                    color: '#ef4444',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 12px',
                  }}
                >
                  <Sparkles size={24} />
                </div>
                <h3
                  style={{
                    fontSize: '15px',
                    fontWeight: 700,
                    margin: '0 0 6px',
                    color: 'var(--fg, #0f172a)',
                  }}
                >
                  How can I help you{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}?
                </h3>
                <p
                  style={{
                    fontSize: '12px',
                    color: 'var(--muted, #64748b)',
                    margin: '0 auto 16px',
                    lineHeight: 1.5,
                    maxWidth: '300px',
                  }}
                >
                  Ask any question about customer orders, delivery tracking, production schedules, or
                  operational risks.
                </p>

                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    textAlign: 'left',
                  }}
                >
                  {SUGGESTED_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSendMessage(prompt)}
                      style={{
                        background: 'var(--surface-hi, #ffffff)',
                        border: '1px solid var(--line, #e2e8f0)',
                        borderRadius: '10px',
                        padding: '9px 12px',
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'var(--fg, #1e293b)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#ef4444'
                        e.currentTarget.style.transform = 'translateY(-1px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--line, #e2e8f0)'
                        e.currentTarget.style.transform = 'none'
                      }}
                    >
                      <span>{prompt}</span>
                      <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '13px' }}>→</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => {
              const isUser = msg.role === 'user'
              return (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                    gap: '4px',
                  }}
                >
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: isUser ? '10px 14px' : '12px 14px',
                      borderRadius: isUser ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                      background: isUser
                        ? 'linear-gradient(135deg, #7c3aed 0%, #6366f1 100%)'
                        : 'var(--surface-hi, #ffffff)',
                      color: isUser ? '#ffffff' : 'var(--fg, #0f172a)',
                      border: isUser ? 'none' : '1px solid var(--line, #e2e8f0)',
                      boxShadow: isUser
                        ? '0 2px 8px rgba(124, 58, 237, 0.25)'
                        : '0 2px 6px rgba(0, 0, 0, 0.04)',
                      fontSize: '12.5px',
                      lineHeight: 1.55,
                      whiteSpace: isUser ? 'pre-wrap' : 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isUser ? msg.content : <FormattedContent content={msg.content} />}
                    {!isUser && msg.steps && msg.steps.length > 0 && (
                      <div style={{ marginTop: '10px' }}>
                        <ToolTrace tools={msg.steps} />
                      </div>
                    )}
                  </div>
                  {msg.timestamp && (
                    <span
                      style={{
                        fontSize: '10px',
                        color: 'var(--muted, #94a3b8)',
                        padding: '0 4px',
                      }}
                    >
                      {msg.timestamp}
                    </span>
                  )}
                </div>
              )
            })}

            {sending && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  alignSelf: 'flex-start',
                  padding: '10px 14px',
                  borderRadius: '16px 16px 16px 2px',
                  background: 'var(--surface-hi, #ffffff)',
                  border: '1px solid var(--line, #e2e8f0)',
                  boxShadow: '0 2px 6px rgba(0, 0, 0, 0.04)',
                  fontSize: '12px',
                  color: 'var(--muted, #64748b)',
                }}
              >
                <div
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '50%',
                    background: '#ef4444',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Bot size={12} color="#ffffff" />
                </div>
                <span>Analyzing order records...</span>
                <span
                  style={{
                    display: 'inline-flex',
                    gap: '3px',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#ef4444', animation: 'bounce 1s infinite 0.1s' }} />
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#ef4444', animation: 'bounce 1s infinite 0.2s' }} />
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#ef4444', animation: 'bounce 1s infinite 0.3s' }} />
                </span>
              </div>
            )}

            {sendError && (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  color: '#991b1b',
                  fontSize: '12px',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
              >
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ flex: 1 }}>{sendError}</div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input */}
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--surface-hi, #ffffff)',
              borderTop: '1px solid var(--line, #e2e8f0)',
            }}
          >
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSendMessage()
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'var(--surface, #f8fafc)',
                border: '1px solid var(--line, #cbd5e1)',
                borderRadius: '12px',
                padding: '6px 8px 6px 12px',
                transition: 'border-color 0.15s, box-shadow 0.15s',
              }}
            >
              <input
                ref={textareaRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about orders, delivery, delays..."
                disabled={sending}
                style={{
                  flex: 1,
                  border: 'none',
                  background: 'transparent',
                  outline: 'none',
                  fontSize: '12.5px',
                  color: 'var(--fg, #0f172a)',
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: input.trim() && !sending
                    ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
                    : 'var(--line, #e2e8f0)',
                  color: input.trim() && !sending ? '#ffffff' : '#94a3b8',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: input.trim() && !sending ? 'pointer' : 'not-allowed',
                  transition: 'all 0.15s ease',
                  flexShrink: 0,
                }}
                title="Send message"
              >
                <Send size={15} />
              </button>
            </form>
            <div
              style={{
                fontSize: '10px',
                color: 'var(--muted, #94a3b8)',
                textAlign: 'center',
                marginTop: '6px',
              }}
            >
              AI responses verify directly with analytical store records
            </div>
          </div>
        </aside>
      )}

      {/* Floating Red Circular Launcher Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
        title="AI Assistant · Order Management Chat"
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '28px',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
          color: '#ffffff',
          border: '3px solid #ffffff',
          boxShadow: '0 8px 24px -4px rgba(239, 68, 68, 0.5), 0 4px 12px rgba(0, 0, 0, 0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          zIndex: 99999,
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          transform: isOpen ? 'rotate(90deg)' : 'scale(1)',
          outline: 'none',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = isOpen ? 'rotate(90deg) scale(1.08)' : 'scale(1.08)'
          e.currentTarget.style.boxShadow = '0 12px 28px -4px rgba(239, 68, 68, 0.6), 0 6px 16px rgba(0, 0, 0, 0.2)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = isOpen ? 'rotate(90deg)' : 'scale(1)'
          e.currentTarget.style.boxShadow = '0 8px 24px -4px rgba(239, 68, 68, 0.5), 0 4px 12px rgba(0, 0, 0, 0.15)'
        }}
      >
        {isOpen ? (
          <X size={24} color="#ffffff" strokeWidth={2.5} />
        ) : (
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', userSelect: 'none' }}>
            <Bot size={26} color="#ffffff" strokeWidth={2.2} />
          </div>
        )}
      </button>
    </>
  )
}
