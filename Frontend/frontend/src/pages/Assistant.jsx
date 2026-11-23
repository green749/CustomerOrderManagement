import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bot, MessageSquarePlus, Send, Sparkles } from 'lucide-react'
import { agentApi } from '../api/agent.api'
import { ordersApi } from '../api/orders.api'
import { Button } from '../components/common/Button'
import { Card } from '../components/common/Card'
import { ErrorState } from '../components/common/ErrorState'
import { Loader } from '../components/common/Loader'
import { Modal } from '../components/common/Modal'
import { ToolTrace } from '../components/agent/ToolTrace'
import { useAuth } from '../context/AuthContext'
import { getErrorMessage } from '../utils/format'
import { canManageApprovals, canUseOperationalFeatures } from '../utils/permissions'
import { useNavigate } from 'react-router-dom'
import { cleanAssistantMessage } from '../components/chat/FloatingChatbot'

const suggestedQuestions = [
  'Which orders are at risk of delay?',
  'Show me the shipment status of my recent orders.',
  'Are there any quality inspection concerns?',
  'Summarize this customer’s orders.',
]

function createMessageId(prefix) {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function messageFromApi(message) {
  return {
    id: message.id ?? createMessageId('message'),
    role: message.role,
    content: message.content ?? '',
    steps: Array.isArray(message.steps) ? message.steps : [],
  }
}

function getToolOrderId(steps) {
  for (const step of steps ?? []) {
    for (const value of [step.input, step.output]) {
      let record = value
      if (typeof value === 'string') {
        try {
          record = JSON.parse(value)
        } catch {
          continue
        }
      }
      const orderId = record?.customer_order_id ?? record?.order_id
      if (typeof orderId === 'string' && orderId.trim()) return orderId.trim()
    }
  }
  return null
}

export default function Assistant() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const canCreateProposal = canUseOperationalFeatures(user)
  const canOpenApprovals = canManageApprovals(user)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [sendError, setSendError] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [sending, setSending] = useState(false)
  const [pendingProposalOrder, setPendingProposalOrder] = useState(null)
  const [proposalSubmitting, setProposalSubmitting] = useState(false)
  const [proposalError, setProposalError] = useState('')
  const [proposalNotice, setProposalNotice] = useState('')
  const messageEndRef = useRef(null)
  const activeConversationRef = useRef(null)
  const requestCounterRef = useRef(0)

  const {
    data: conversations = [],
    isLoading: loadingConversations,
    refetch: loadConversations,
    error: convQueryError,
  } = useQuery({
    queryKey: ['agent-conversations'],
    queryFn: () => agentApi.getConversations(),
    staleTime: 60 * 1000,
  })
  const conversationError = convQueryError ? getErrorMessage(convQueryError) : ''

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  const selectConversation = async (id) => {
    activeConversationRef.current = id
    setConversationId(id)
    setMessages([])
    setHistoryError('')
    setLoadingHistory(true)
    try {
      const result = await agentApi.getMessages(id)
      if (activeConversationRef.current !== id) return
      setMessages(result.map(messageFromApi))
    } catch (error) {
      if (activeConversationRef.current !== id) return
      setHistoryError(getErrorMessage(error))
    } finally {
      if (activeConversationRef.current === id) {
        setLoadingHistory(false)
      }
    }
  }

  const startNewConversation = () => {
    activeConversationRef.current = null
    setConversationId(null)
    setMessages([])
    setHistoryError('')
    setSendError('')
    setInput('')
  }

  const sendMessage = async (event) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || sending) return

    const requestNumber = ++requestCounterRef.current
    const pendingUserMessage = { id: createMessageId('pending'), role: 'user', content: text, steps: [] }
    const targetConversationId = conversationId

    setMessages((current) => [...current, pendingUserMessage])
    setInput('')
    setSending(true)
    setSendError('')

    try {
      const response = await agentApi.sendMessage(text, targetConversationId)
      if (requestCounterRef.current !== requestNumber) {
        return
      }
      if (typeof response?.answer !== 'string' || !response.conversation_id) {
        throw new Error('The agent response did not match the backend chat schema.')
      }
      if (targetConversationId !== response.conversation_id) {
        activeConversationRef.current = response.conversation_id
      }
      setConversationId(response.conversation_id)
      setMessages((current) => {
        const withoutPending = current.filter((message) => message.id !== pendingUserMessage.id)
        const nextMessages = [...withoutPending, pendingUserMessage]
        const assistantMessage = {
          id: response.message_id ?? createMessageId('assistant'),
          role: 'assistant',
          content: response.answer,
          steps: Array.isArray(response.steps) ? response.steps : [],
        }
        return [...nextMessages, assistantMessage]
      })
      loadConversations()
    } catch (error) {
      if (requestCounterRef.current !== requestNumber) {
        return
      }
      setMessages((current) => current.filter((message) => message.id !== pendingUserMessage.id))
      setInput(text)
      setSendError(getErrorMessage(error))
    } finally {
      if (requestCounterRef.current === requestNumber) {
        setSending(false)
      }
    }
  }

  const confirmCreateProposal = async () => {
    if (!pendingProposalOrder) return
    setProposalSubmitting(true)
    setProposalError('')
    try {
      await ordersApi.createCommitmentProposal(pendingProposalOrder, { recommended_by: 'agent' })
      setProposalNotice(`A commitment proposal for ${pendingProposalOrder} was submitted to Approvals.`)
      setPendingProposalOrder(null)
      if (canOpenApprovals) navigate('/approvals')
    } catch (requestError) {
      setProposalError(getErrorMessage(requestError, 'Could not create the commitment proposal.'))
    } finally {
      setProposalSubmitting(false)
    }
  }

  return (
    <div className="assistant-page">
      <div className="assistant-layout">
        <Card as="aside" className="conversation-sidebar">
          <div className="conversation-sidebar-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Conversations ({conversations.length})</span>
            <Button type="button" variant="secondary" onClick={startNewConversation} disabled={sending} style={{ padding: '3px 8px', fontSize: 11, minHeight: 26, gap: 4 }}>
              <MessageSquarePlus size={13} /> New
            </Button>
          </div>
          {loadingConversations ? <Loader label="Loading conversations" /> : conversationError ? (
            <ErrorState title="Conversations unavailable" message={conversationError} onRetry={loadConversations} />
          ) : conversations.length ? (
            <div className="conversation-list">
              {conversations.map((conversation) => (
                <button key={conversation.id} type="button" className={`conversation-item${conversation.id === conversationId ? ' active' : ''}`} onClick={() => selectConversation(conversation.id)} disabled={sending}>
                  <span className="conversation-icon"><MessageSquarePlus size={15} /></span>
                  <span className="conversation-copy"><strong>{conversation.title || 'Untitled conversation'}</strong><small>{conversation.message_count ?? 0} messages</small></span>
                </button>
              ))}
            </div>
          ) : <p className="conversation-empty">Your conversations will appear here.</p>}
        </Card>

        <Card as="section" className="chat-panel">
          <div className="chat-panel-header"><span className="assistant-avatar"><Bot size={18} /></span><div><strong>Order Management Agent</strong><small>Responses come from the connected backend agent.</small></div></div>
          <div className="chat-messages" aria-live="polite">
            {proposalNotice && <p className="workflow-success" role="status">{proposalNotice}{!canOpenApprovals && ' A manager can review it in Approvals.'}</p>}
            {!messages.length && !loadingHistory && (
              <div className="chat-welcome">
                <span className="chat-welcome-icon"><Sparkles size={20} /></span>
                <h2>How can I help you today{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}?</h2>
                <p>Ask a question to get started. The assistant will report an error if its service is unavailable.</p>
                <div className="suggested-questions">{suggestedQuestions.map((question) => <button key={question} type="button" onClick={() => setInput(question)}>{question}</button>)}</div>
              </div>
            )}
            {loadingHistory && <Loader label="Loading conversation" />}
            {historyError && <ErrorState title="Could not load messages" message={historyError} onRetry={() => conversationId && selectConversation(conversationId)} />}
            {messages.map((message) => (
              <article key={message.id} className={`chat-message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}>
                <div className="message-avatar">{message.role === 'user' ? (user?.full_name?.[0] ?? 'Y') : <Bot size={16} />}</div>
                <div className="message-content">
                  <p style={{ whiteSpace: 'pre-wrap' }}>{message.role === 'assistant' ? cleanAssistantMessage(message.content) : message.content}</p>
                  {message.steps.length > 0 && <ToolTrace tools={message.steps} />}
                  {message.role === 'assistant' && canCreateProposal && getToolOrderId(message.steps) && (
                    <Button type="button" variant="secondary" onClick={() => { setProposalError(''); setPendingProposalOrder(getToolOrderId(message.steps)) }}>
                      Create proposal
                    </Button>
                  )}
                </div>
              </article>
            ))}
            {sending && <div className="chat-message assistant-message"><div className="message-avatar"><Bot size={16} /></div><div className="message-content"><Loader label="Agent is responding" /></div></div>}
            <div ref={messageEndRef} />
          </div>
          {sendError && <div className="chat-send-error" role="alert">{sendError}</div>}
          {proposalError && <div className="chat-send-error" role="alert">{proposalError}</div>}
          <form className="chat-composer" onSubmit={sendMessage}>
            <label className="sr-only" htmlFor="assistant-message">Message the order assistant</label>
            <textarea id="assistant-message" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="Ask about your orders..." rows={1} disabled={sending} />
            <Button type="submit" disabled={!input.trim() || sending} aria-label="Send message"><Send size={16} /></Button>
          </form>
          <p className="chat-disclaimer">AI responses may require verification against the source records.</p>
        </Card>
      </div>
      <Modal
        open={Boolean(pendingProposalOrder)}
        onClose={() => { if (!proposalSubmitting) setPendingProposalOrder(null) }}
        title="Create commitment proposal"
      >
        <p>Submit a promise-date proposal for <strong>{pendingProposalOrder}</strong>? The backend will calculate the recommendation and send it to the Approvals queue.</p>
        <div className="proposal-actions">
          <Button type="button" variant="secondary" onClick={() => setPendingProposalOrder(null)} disabled={proposalSubmitting}>Cancel</Button>
          <Button type="button" onClick={confirmCreateProposal} disabled={proposalSubmitting}>{proposalSubmitting ? 'Submitting…' : 'Confirm proposal'}</Button>
        </div>
      </Modal>
    </div>
  )
}
