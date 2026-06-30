/**
 * ToolsSection — настройки раздела «Инструменты» (Система).
 *
 * Получает инструменты из GET /api/tools, рисует карточками по категориям.
 * Toggle пишет в POST /api/tools/toggle, ответ применяется оптимистично
 * (UI обновляется сразу, на ошибке — откат).
 *
 * Display / category берутся с бэка из config/tools.yaml (если объявлено);
 * scope (all/head/primary/builtin) и dangerous — из chat/router.py.
 *
 * Builtin-инструменты (память) показываются как «always on», переключатель
 * заблокирован. Это потому что они зашиты в каждого агента на бэке —
 * отключить нельзя даже через settings.yaml.
 */

import { useEffect, useState, useCallback } from 'react'
import { SettingsCard } from '../SettingsCard'

type ToolScope = 'all' | 'head' | 'primary' | 'builtin'

interface Tool {
  name: string
  display: string
  description: string
  category: string
  scope: ToolScope
  dangerous: boolean
  implemented: boolean
  enabled: boolean
}

// Маппинг scope → человекочитаемая метка для тултипа карточки.
const SCOPE_LABEL: Record<ToolScope, string> = {
  all: 'Доступен всем агентам',
  head: 'Только главный агент и главы отделов',
  primary: 'Только главный агент системы',
  builtin: 'Всегда включён, нельзя отключить',
}

// Маппинг scope → pill в карточке (короткий, 3-4 буквы).
const SCOPE_PILL: Record<ToolScope, string> = {
  all: 'all',
  head: 'head',
  primary: 'prim',
  builtin: 'builtin',
}

// Кэш переводов категорий tools.yaml → человекочитаемые имена.
// Ключи должны совпадать с `category` в config/tools.yaml.
// Если категория не перечислена — берём её как есть (lowercase).
const CATEGORY_LABEL: Record<string, string> = {
  files: 'Файлы',
  code: 'Код и терминал',
  web: 'Веб',
  memory: 'Память',
  communication: 'Коммуникация',
  tasks: 'Задачи',
  skills: 'Скиллы',
  head_protocol: 'Протокол Главы',
  system: 'Система',
  other: 'Прочее',
}

// Сортировка категорий для UI — логичный порядок, не алфавитный.
const CATEGORY_ORDER: string[] = [
  'Файлы', 'Код и терминал', 'Память', 'Веб',
  'Коммуникация', 'Задачи', 'Скиллы', 'Протокол Главы',
  'Система', 'Прочее',
]

/**
 * Утилита: группировка инструментов по категории (с человекочитаемым лейблом),
 * с учётом порядка CATEGORY_ORDER. Категории не из списка идут в конец.
 */
function groupByCategory(tools: Tool[]): Array<{ label: string; items: Tool[] }> {
  const buckets = new Map<string, Tool[]>()
  for (const t of tools) {
    const label = CATEGORY_LABEL[t.category] || t.category
    if (!buckets.has(label)) buckets.set(label, [])
    buckets.get(label)!.push(t)
  }
  const entries = Array.from(buckets.entries())
  entries.sort(([a], [b]) => {
    const ia = CATEGORY_ORDER.indexOf(a)
    const ib = CATEGORY_ORDER.indexOf(b)
    if (ia === -1 && ib === -1) return a.localeCompare(b)
    if (ia === -1) return 1
    if (ib === -1) return -1
    return ia - ib
  })
  return entries.map(([label, items]) => ({
    label,
    items: items.sort((x, y) => x.name.localeCompare(y.name)),
  }))
}

export function ToolsSection() {
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Имена инструментов, которые сейчас в процессе toggle (для disabled-спиннера).
  const [pending, setPending] = useState<Set<string>>(new Set())

  // Загрузка списка при маунте.
  useEffect(() => {
    let cancelled = false
    fetch('/api/tools/settings/')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: unknown) => {
        if (cancelled) return
        // Server might proxy through Vite and return HTML index for unknown
        // routes when the backend is down. Guard against non-array payloads
        // so we don't poison state with a string/object and crash later
        // in .filter/.map with "tools is not iterable".
        if (!Array.isArray(data)) {
          throw new Error('Сервер вернул неожиданный ответ (ожидался JSON-массив)')
        }
        setTools(data)
        setError(null)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Не удалось загрузить инструменты')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // Оптимистичный toggle: сразу обновляем UI, на ошибке — откатываем.
  const handleToggle = useCallback(async (name: string, nextEnabled: boolean) => {
    // builtin — клиентский guard. Бэкенд тоже отдаст 404 но мы блокируем заранее.
    if (nextEnabled === false) {
      // disable всегда разрешён (если не builtin)
    }
    const before = tools.find(t => t.name === name)?.enabled
    if (before === nextEnabled) return  // без изменений

    setTools(prev => prev.map(t => t.name === name ? { ...t, enabled: nextEnabled } : t))
    setPending(prev => new Set(prev).add(name))

    try {
      const r = await fetch('/api/tools/settings/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, enabled: nextEnabled }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
    } catch (err) {
      // Откат при ошибке.
      setTools(prev => prev.map(t => t.name === name ? { ...t, enabled: before ?? !nextEnabled } : t))
      setError(`Не удалось сохранить изменение для ${name}: ${err instanceof Error ? err.message : 'unknown'}`)
    } finally {
      setPending(prev => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
    }
  }, [tools])

  const grouped = groupByCategory(tools)
  const enabledCount = tools.filter(t => t.enabled).length

  return (
    <div className="settings-sections">
      <SettingsCard
        title="Инструменты агентов"
        badge={`${enabledCount} из ${tools.length} включено`}
        description="Глобальный выключатель инструментов: при отключении агент перестаёт видеть этот инструмент в своём системном промте. Изменения применяются мгновенно, перезапуск не требуется."
        loading={loading}
        loadingText="Загрузка инструментов..."
      >
        {error && (
          <div className="settings-error" role="alert">
            {error}
          </div>
        )}
        {!loading && tools.length === 0 && (
          <p style={{ color: 'var(--text-dim)', fontSize: 13 }}>
            Нет зарегистрированных инструментов.
          </p>
        )}
        {!loading && tools.length > 0 && grouped.map(group => (
          <section key={group.label} className="tools-category">
            <h3 className="tools-category-title">
              {group.label}
              <span className="tools-category-count">
                {group.items.filter(t => t.enabled).length}/{group.items.length}
              </span>
            </h3>
            <div className="tools-grid">
              {group.items.map(tool => (
                <ToolCard
                  key={tool.name}
                  tool={tool}
                  pending={pending.has(tool.name)}
                  onToggle={(next) => handleToggle(tool.name, next)}
                />
              ))}
            </div>
          </section>
        ))}
      </SettingsCard>
    </div>
  )
}

interface ToolCardProps {
  tool: Tool
  pending: boolean
  onToggle: (nextEnabled: boolean) => void
}

function ToolCard({ tool, pending, onToggle }: ToolCardProps) {
  const isBuiltin = tool.scope === 'builtin'
  const isDisabled = isBuiltin || !tool.enabled

  // Подсказка для заголовка карточки — что значит scope.
  const titleHint = SCOPE_LABEL[tool.scope]

  return (
    <div
      className={`tool-card ${isDisabled ? 'tool-card-off' : ''} ${pending ? 'tool-card-pending' : ''}`}
      title={titleHint}
    >
      <div className="tool-card-top">
        <div className="tool-card-name">
          <span>{tool.display}</span>
          {tool.dangerous && (
            <span className="tool-card-danger" title="Может менять систему (файлы, терминал, выполнение кода)">
              ⚠
            </span>
          )}
        </div>
        {/* Базовый checkbox — стилизуется через уже существующий .settings-toggle
            в settings.css. Не используем <Toggle/> component — у него
            горизонтальный field-row layout, а нам нужен компактный. */}
        <label
          className="settings-toggle tool-card-toggle"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={tool.enabled}
            disabled={isBuiltin || pending}
            onChange={e => onToggle(e.target.checked)}
          />
        </label>
      </div>
      <p className="tool-card-desc" title={tool.description}>
        {tool.description}
      </p>
      <div className="tool-card-meta">
        <span className="tool-card-pill">{SCOPE_PILL[tool.scope]}</span>
        {!tool.implemented && (
          <span className="tool-card-pill tool-card-pill-stub">stub</span>
        )}
        {isBuiltin && (
          <span className="tool-card-pill tool-card-pill-locked">always</span>
        )}
      </div>
    </div>
  )
}
