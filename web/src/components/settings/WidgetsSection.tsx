/**
 * WidgetsSection — library of available widgets.
 * Shows all widgets as cards; placed ones are dimmed.
 * Drag to left/right panel zones from the main page.
 */
import { useState, useEffect } from 'react'
import { API_BASE } from '../../config'
import { WIDGET_META, type WidgetType } from '../WidgetDropZone'

interface WidgetLayout {
  left: WidgetType[]
  right: WidgetType[]
}

const ALL_WIDGETS = Object.keys(WIDGET_META) as WidgetType[]

export function WidgetsSection() {
  const [layout, setLayout] = useState<WidgetLayout>({ left: [], right: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/api/widgets/layout`)
      .then(r => r.ok ? r.json() : { left: [], right: [] })
      .then(data => {
        setLayout({
          left: data.left || [],
          right: data.right || [],
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const placed = new Set([...layout.left, ...layout.right])

  if (loading) {
    return <div className="settings-hint">Загрузка...</div>
  }

  return (
    <div>
      <p className="settings-hint" style={{ marginBottom: '16px' }}>
        Виджеты, размещённые на панели, отображаются на главной странице.
        Перетащите виджет из боковой панели сюда, чтобы убрать его.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {ALL_WIDGETS.map(id => {
          const meta = WIDGET_META[id]
          const isPlaced = placed.has(id)
          return (
            <div
              key={id}
              className="widget-library-card"
              style={{
                opacity: isPlaced ? 0.45 : 1,
                pointerEvents: isPlaced ? 'none' : 'auto',
              }}
            >
              <span className="widget-library-icon">{meta.icon}</span>
              <span className="widget-library-label">{meta.label}</span>
              {isPlaced && (
                <span className="widget-library-badge">На панели</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
