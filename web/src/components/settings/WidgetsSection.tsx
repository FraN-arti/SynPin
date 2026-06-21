/**
 * WidgetsSection — library of available widgets.
 * Shows all widgets as cards with add/remove buttons.
 * Placed widgets show which zone they're in and can be removed.
 */
import { useState, useEffect, useCallback } from 'react'
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

  const loadLayout = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/widgets/layout`)
      if (res.ok) {
        const data = await res.json()
        setLayout({ left: data.left || [], right: data.right || [] })
      }
    } catch {}
    setLoading(false)
  }, [])

  useEffect(() => { loadLayout() }, [loadLayout])

  const saveLayout = useCallback(async (next: WidgetLayout) => {
    setLayout(next)
    await fetch(`${API_BASE}/api/widgets/layout`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(next),
    })
    window.dispatchEvent(new Event('synpin-widgets-changed'))
  }, [])

  const addToZone = useCallback((id: WidgetType, zone: 'left' | 'right') => {
    saveLayout({
      ...layout,
      [zone]: [...layout[zone], id],
    })
  }, [layout, saveLayout])

  const removeFromZone = useCallback((id: WidgetType) => {
    saveLayout({
      left: layout.left.filter(w => w !== id),
      right: layout.right.filter(w => w !== id),
    })
  }, [layout, saveLayout])

  if (loading) {
    return <div className="settings-hint">Загрузка...</div>
  }

  return (
    <div>
      <p className="settings-hint" style={{ marginBottom: '16px' }}>
        Управляйте виджетами на главной панели. Добавьте виджет в левую или правую зону.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {ALL_WIDGETS.map(id => {
          const meta = WIDGET_META[id]
          const leftIdx = layout.left.indexOf(id)
          const rightIdx = layout.right.indexOf(id)
          const isPlaced = leftIdx !== -1 || rightIdx !== -1
          const zone = leftIdx !== -1 ? 'left' : rightIdx !== -1 ? 'right' : null

          return (
            <div
              key={id}
              className="widget-library-card"
              style={{ opacity: isPlaced ? 0.65 : 1 }}
            >
              <span className="widget-library-icon">{meta.icon}</span>
              <span className="widget-library-label">{meta.label}</span>

              {isPlaced ? (
                <div className="widget-library-actions">
                  <span className="widget-library-badge">
                    {zone === 'left' ? 'Лево' : 'Право'}
                  </span>
                  <button
                    className="widget-lib-btn remove"
                    onClick={() => removeFromZone(id)}
                    title="Убрать с панели"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <div className="widget-library-actions">
                  <button
                    className="widget-lib-btn add"
                    onClick={() => addToZone(id, 'left')}
                    title="Добавить в левую зону"
                  >
                    ◀ Лево
                  </button>
                  <button
                    className="widget-lib-btn add"
                    onClick={() => addToZone(id, 'right')}
                    title="Добавить в правую зону"
                  >
                    Право ▶
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
