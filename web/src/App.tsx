import { useState, useRef, useEffect } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    // TODO: Replace with real API call
    setTimeout(() => {
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Это шаблон ответа. Здесь будет ответ от SynPin агента.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsTyping(false)
    }, 1500)
  }

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-violet-600 flex items-center justify-center font-bold text-sm">
              S
            </div>
            <span className="font-semibold">SynPin</span>
          </div>
        </div>

        <button className="mx-3 mt-3 px-3 py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-sm text-left flex items-center gap-2 transition-colors">
          <span className="text-lg">+</span>
          Новый чат
        </button>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="px-3 py-1.5 text-xs text-gray-500 uppercase tracking-wider">Сегодня</div>
          <button className="w-full px-3 py-2 rounded-lg text-sm text-left hover:bg-gray-800 transition-colors truncate">
            Архитектура API
          </button>
          <button className="w-full px-3 py-2 rounded-lg text-sm text-left hover:bg-gray-800 transition-colors truncate">
            Тесты для auth
          </button>
        </nav>

        <div className="p-3 border-t border-gray-800">
          <button className="w-full px-3 py-2 rounded-lg text-sm text-left hover:bg-gray-800 transition-colors flex items-center gap-2">
            <span>⚙️</span> Настройки
          </button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col">
        {messages.length === 0 ? (
          // Empty state
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <div className="w-12 h-12 rounded-xl bg-violet-600 flex items-center justify-center font-bold text-xl mb-4">
              S
            </div>
            <h1 className="text-2xl font-semibold mb-8">Чем могу помочь?</h1>
          </div>
        ) : (
          // Messages
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto py-6 space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-4 px-4 ${msg.role === 'assistant' ? '' : 'justify-end'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-lg bg-violet-600 flex-shrink-0 flex items-center justify-center font-bold text-xs">
                      S
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-violet-600 text-white'
                        : 'bg-gray-800 text-gray-100'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-lg bg-gray-600 flex-shrink-0 flex items-center justify-center font-bold text-xs">
                      U
                    </div>
                  )}
                </div>
              ))}
              {isTyping && (
                <div className="flex gap-4 px-4">
                  <div className="w-8 h-8 rounded-lg bg-violet-600 flex-shrink-0 flex items-center justify-center font-bold text-xs">
                    S
                  </div>
                  <div className="bg-gray-800 rounded-2xl px-4 py-3">
                    <div className="flex gap-1.5">
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-800 p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Спроси что-нибудь..."
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 pr-12 text-sm placeholder-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors"
              />
              <button
                type="submit"
                disabled={!input.trim() || isTyping}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-500 flex items-center justify-center transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2 text-center">
              SynPin может ошибаться. Проверяй важную информацию.
            </p>
          </form>
        </div>
      </main>
    </div>
  )
}

export default App
