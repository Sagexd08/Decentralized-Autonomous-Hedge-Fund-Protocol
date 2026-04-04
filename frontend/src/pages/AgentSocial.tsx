import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, Bot, User, Heart, Radio, Play, Square, Send, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { API_BASE_URL, WS_SOCIAL_URL } from '../utils/api'

interface Comment {
  id: number
  agent_name: string
  content: string
  timestamp: number
}

interface Post {
  id: number
  agent_name: string
  content: string
  timestamp: number
  sentiment: string
  token?: string
  likes: number
  comments: Comment[]
  is_ai: boolean
  avatar: string
  color: string
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const SENTIMENT_STYLES: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  bullish:  { icon: TrendingUp,   color: 'text-green',    bg: 'bg-green/10 border-green/20' },
  bearish:  { icon: TrendingDown, color: 'text-red-400',  bg: 'bg-red-500/10 border-red-500/20' },
  neutral:  { icon: Minus,        color: 'text-slate-400', bg: 'bg-slate-700/50 border-border' },
  news:     { icon: Radio,        color: 'text-gold',     bg: 'bg-gold/10 border-gold/20' },
}

function PostCard({ post, onLike }: { post: Post; onLike: (id: number) => void }) {
  const [showComments, setShowComments] = useState(false)
  const s = SENTIMENT_STYLES[post.sentiment] ?? SENTIMENT_STYLES.neutral
  const SIcon = s.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card"
    >
      <div className="flex items-start gap-3">
        {}
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 text-black"
          style={{ background: post.color }}
        >
          {post.avatar}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-bold text-white">{post.agent_name}</span>
            {post.is_ai && (
              <span className="flex items-center gap-0.5 text-xs text-cyan bg-cyan/10 px-1.5 py-0.5 rounded-full">
                <Bot size={9} /> AI
              </span>
            )}
            <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${s.bg} ${s.color}`}>
              <SIcon size={10} />
              {post.sentiment}
            </span>
            {post.token && (
              <span className="text-xs font-mono text-cyan bg-cyan/10 px-1.5 py-0.5 rounded">{post.token}</span>
            )}
          </div>

          <p className="text-sm text-slate-300 leading-relaxed mb-2">{post.content}</p>

          {}
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <button
              onClick={() => onLike(post.id)}
              className="flex items-center gap-1 hover:text-red-400 transition-colors"
            >
              <Heart size={12} />
              {post.likes}
            </button>
            <button
              onClick={() => setShowComments(s => !s)}
              className="flex items-center gap-1 hover:text-cyan transition-colors"
            >
              <MessageSquare size={12} />
              {post.comments.length} {showComments ? '▲' : '▼'}
            </button>
            <span className="ml-auto">{timeAgo(post.timestamp)}</span>
          </div>

          {}
          {showComments && post.comments.length > 0 && (
            <div className="mt-2 space-y-1.5 pl-3 border-l border-border">
              {post.comments.map((c, i) => (
                <div key={i} className="text-xs">
                  <span className="font-medium text-slate-400">{c.agent_name}: </span>
                  <span className="text-slate-500">{c.content}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function HumanFeed() {
  const [posts, setPosts] = useState<Post[]>([])
  const [input, setInput] = useState('')
  const [username, setUsername] = useState('You')

  const handlePost = async () => {
    if (!input.trim()) return
    try {
      await fetch(`${API_BASE_URL}/api/social/human-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: input.trim(), username }),
      })
      setInput('')
    } catch {

      const p: Post = {
        id: Date.now(), agent_name: username, content: input.trim(),
        timestamp: Date.now() / 1000, sentiment: 'neutral', likes: 0,
        comments: [], is_ai: false, avatar: username.slice(0, 2).toUpperCase(), color: '#64748b',
      }
      setPosts(prev => [p, ...prev])
      setInput('')
    }
  }

  return (
    <div className="space-y-4">
      {}
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <User size={14} className="text-slate-400" />
          <input
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Your name"
            className="text-xs bg-transparent text-slate-400 border-b border-border focus:outline-none w-32"
          />
        </div>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handlePost() }}
          placeholder="Share your market thoughts... (⌘+Enter to post)"
          rows={3}
          className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan/40 resize-none"
        />
        <div className="flex justify-end">
          <button onClick={handlePost} disabled={!input.trim()} className="btn-primary flex items-center gap-2 disabled:opacity-40">
            <Send size={13} /> Post
          </button>
        </div>
      </div>

      {posts.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-sm">
          Be the first to post. Agents will respond to your messages.
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map(p => (
            <PostCard key={p.id} post={p} onLike={id => setPosts(prev => prev.map(x => x.id === id ? { ...x, likes: x.likes + 1 } : x))} />
          ))}
        </div>
      )}
    </div>
  )
}

function AIAgentFeed() {
  const [posts, setPosts] = useState<Post[]>([])
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket(WS_SOCIAL_URL)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'history') {
          setPosts(msg.posts.reverse())
        } else if (msg.type === 'post') {
          setPosts(prev => [msg.post, ...prev].slice(0, 100))
        } else if (msg.type === 'comment') {
          setPosts(prev => prev.map(p =>
            p.id === msg.post_id
              ? { ...p, comments: [...p.comments, msg.comment] }
              : p
          ))
        }
      } catch {  }
    }

    fetch(`${API_BASE_URL}/api/social/status`)
      .then(r => r.json())
      .then(d => setRunning(d.running))
      .catch(() => {})

    return () => { ws.onclose = null; ws.close() }
  }, [])

  const toggleCommunication = async () => {
    setLoading(true)
    try {
      const endpoint = running ? '/api/social/stop' : '/api/social/start'
      const res = await fetch(`${API_BASE_URL}${endpoint}`, { method: 'POST' })
      const data = await res.json()
      setRunning(data.running ?? !running)
    } catch {  }
    setLoading(false)
  }

  const handleLike = (id: number) => {
    setPosts(prev => prev.map(p => p.id === id ? { ...p, likes: p.likes + 1 } : p))
  }

  return (
    <div className="space-y-4">
      {}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {running && (
            <span className="flex items-center gap-1.5 text-xs text-green font-mono">
              <Radio size={12} className="animate-pulse" />
              Agents communicating live via Gemini AI
            </span>
          )}
          {!running && (
            <span className="text-xs text-slate-500">Click to start AI agent communication</span>
          )}
        </div>
        <button
          onClick={toggleCommunication}
          disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
            running
              ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20'
              : 'bg-green/10 text-green border border-green/20 hover:bg-green/20'
          } disabled:opacity-50`}
        >
          {running ? <Square size={14} /> : <Play size={14} />}
          {loading ? 'Loading...' : running ? 'Stop Communication' : 'Start Communication'}
        </button>
      </div>

      {}
      {posts.length === 0 ? (
        <div className="text-center py-12 space-y-3">
          <Bot size={40} className="text-slate-600 mx-auto" />
          <p className="text-slate-500 text-sm">
            {running ? 'Agents are warming up... first post coming soon.' : 'Press "Start Communication" to activate AI agents.'}
          </p>
        </div>
      ) : (
        <AnimatePresence initial={false}>
          <div className="space-y-3">
            {posts.map(p => (
              <PostCard key={p.id} post={p} onLike={handleLike} />
            ))}
          </div>
        </AnimatePresence>
      )}
    </div>
  )
}

export default function AgentSocial() {
  const [tab, setTab] = useState<'ai' | 'human'>('ai')

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <MessageSquare size={20} className="text-cyan" />
            Agent Social Feed
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">AI agents powered by Gemini · Human community</p>
        </div>
      </div>

      {}
      <div className="flex items-center gap-1 bg-surface border border-border rounded-xl p-1 w-fit">
        <button
          onClick={() => setTab('ai')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            tab === 'ai' ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <Bot size={14} />
          AI Agent Feed
        </button>
        <button
          onClick={() => setTab('human')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            tab === 'human' ? 'bg-purple/10 text-purple border border-purple/20' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          <User size={14} />
          Human Feed
        </button>
      </div>

      {}
      <div style={{ display: tab === 'ai' ? 'block' : 'none' }}>
        <AIAgentFeed />
      </div>
      <div style={{ display: tab === 'human' ? 'block' : 'none' }}>
        <HumanFeed />
      </div>
    </div>
  )
}
