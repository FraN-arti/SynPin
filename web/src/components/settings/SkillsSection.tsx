/**
 * SkillsSection — настройки раздела «Скиллы» (Система).
 *
 * Получает скиллы из GET /api/skills/settings/, рисует карточками
 * по категориям. Toggle пишет в POST /api/skills/settings/toggle.
 * Оптимистичный UI с откатом на ошибке.
 *
 * Структура карточек повторяет ToolsSection — единый визуальный язык.
 */

import { useEffect, useState, useCallback } from 'react'
import { SettingsCard } from '../SettingsCard'

interface Skill {
  name: string
  description: string
  category: string
  enabled: boolean
}

// Кэш переводов категорий → человекочитаемые имена.
const CATEGORY_LABEL: Record<string, string> = {
  meta: 'Мета-скиллы',
  general: 'Общие',
  code: 'Код',
  protocol: 'Протоколы',
  test: 'Тестовые',
}

// Сортировка категорий для UI.
const CATEGORY_ORDER: string[] = [
  'Мета-скиллы', 'Общие', 'Код', 'Протоколы', 'Прочее', 'Тестовые',
]

function groupByCategory(skills: Skill[]): Array<{ label: string; items: Skill[] }> {
  const buckets = new Map<string, Skill[]>()
  for (const s of skills) {
    const label = CATEGORY_LABEL[s.category] || s.category
    if (!buckets.has(label)) buckets.set(label, [])
    buckets.get(label)!.push(s)
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

export function SkillsSection() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    fetch('/api/skills/settings/')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: unknown) => {
        if (cancelled) return
        if (!Array.isArray(data)) {
          throw new Error('Сервер вернул неожиданный ответ (ожидался JSON-массив)')
        }
        setSkills(data)
        setError(null)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Не удалось загрузить скиллы')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const handleToggle = useCallback(async (name: string, nextEnabled: boolean) => {
    const before = skills.find(s => s.name === name)?.enabled
    if (before === nextEnabled) return

    setSkills(prev => prev.map(s => s.name === name ? { ...s, enabled: nextEnabled } : s))
    setPending(prev => new Set(prev).add(name))

    try {
      const r = await fetch('/api/skills/settings/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, enabled: nextEnabled }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
    } catch (err) {
      setSkills(prev => prev.map(s => s.name === name ? { ...s, enabled: before ?? !nextEnabled } : s))
      setError(`Не удалось сохранить изменение для ${name}: ${err instanceof Error ? err.message : 'unknown'}`)
    } finally {
      setPending(prev => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
    }
  }, [skills])

  const grouped = groupByCategory(skills)
  const enabledCount = skills.filter(s => s.enabled).length

  return (
    <div className="settings-sections">
      <SettingsCard
        title="Скиллы системы"
        badge={`${enabledCount} из ${skills.length} включено`}
        description="Скиллы — это процедуры и подходы для решения задач. При отключении агент перестаёт видеть скилл в системном промте. Создавать и редактировать скиллы может только главный агент через инструмент skill_manage."
        loading={loading}
        loadingText="Загрузка скиллов..."
      >
        {error && (
          <div className="settings-error" role="alert">
            {error}
          </div>
        )}
        {!loading && skills.length === 0 && (
          <p style={{ color: 'var(--text-dim)', fontSize: 13 }}>
            Нет зарегистрированных скиллов. Главный агент может создать новый через skill_manage.
          </p>
        )}
        {!loading && skills.length > 0 && grouped.map(group => (
          <section key={group.label} className="tools-category">
            <h3 className="tools-category-title">
              {group.label}
              <span className="tools-category-count">
                {group.items.filter(s => s.enabled).length}/{group.items.length}
              </span>
            </h3>
            <div className="tools-grid">
              {group.items.map(skill => (
                <SkillCard
                  key={skill.name}
                  skill={skill}
                  pending={pending.has(skill.name)}
                  onToggle={(next) => handleToggle(skill.name, next)}
                />
              ))}
            </div>
          </section>
        ))}
      </SettingsCard>
    </div>
  )
}

interface SkillCardProps {
  skill: Skill
  pending: boolean
  onToggle: (nextEnabled: boolean) => void
}

function SkillCard({ skill, pending, onToggle }: SkillCardProps) {
  const isOff = !skill.enabled

  return (
    <div
      className={`tool-card skill-card ${isOff ? 'tool-card-off' : ''} ${pending ? 'tool-card-pending' : ''}`}
    >
      <div className="tool-card-top">
        <div className="tool-card-name">
          <span>{skill.name}</span>
        </div>
        <label
          className="settings-toggle tool-card-toggle"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={skill.enabled}
            disabled={pending}
            onChange={e => onToggle(e.target.checked)}
          />
        </label>
      </div>
      <p className="tool-card-desc" title={skill.description}>
        {skill.description}
      </p>
      <div className="tool-card-meta">
        <span className="tool-card-pill">{skill.category}</span>
      </div>
    </div>
  )
}
