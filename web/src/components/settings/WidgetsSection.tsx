/**
 * WidgetsSection — library of available widgets.
 * Cards are draggable into left/right panel zones via @dnd-kit.
 * Syncs with backend via WebSocket.
 */
import { useState, useEffect, useCallback } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { API_BASE } from '../../config'
import { WIDGET_META, type WidgetType } from '../WidgetDropZone'

interface WidgetLayout {
  left: WidgetType[]
  right: WidgetType[]
}

const ALL_WIDGETS = Object.keys(WIDGET_META) as WidgetType[]

function DraggableWidgetCard({
  id,
  isPlaced,
  zone,
}: {
  id: WidgetType
  isPlaced: boolean
  zone: 'left' | 'right' | null
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `lib-${id}`,
    data: { type: 'widget', widgetId: id },
  })

  const meta = WIDGET_META[id]
  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : isPlaced ? 0.4 : 1,
    zIndex: isDragging ? 100 : undefined,
    pointerEvents: isDragging ? 'none' : 'auto',
  }

  return (
    <div
      ref={setNodeRef}
      className={`widget-library-card ${isDragging ? 'dragging' : ''} ${isPlaced ? 'placed' : ''}`}
      style={style}
      {...listeners}
      {...attributes}
    >
      <span className="widget-library-icon">{meta.icon}</span>
      <span className="widget-library-label">{meta.label}</span>
      {isPlaced && (
        <span className="widget-library-badge">
          {zone === 'left' ? 'Левая панель' : 'Правая панель'}
        </span>
      )}
    </div>
  )
}

export function WidgetsSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void }) {
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

  // WS sync — update when layout changes from other clients or main page
  useEffect(() => {
    if (!wsOn) return
    const off = wsOn('widgets:layout_changed', (msg: any) => {
      if (msg.layout) setLayout(msg.layout)
    })
    return off
  }, [wsOn])

  // Also listen for the custom DOM event (when user drags on main page)
  useEffect(() => {
    const handler = () => loadLayout()
    window.addEventListener('synpin-widgets-changed', handler)
    return () => window.removeEventListener('synpin-widgets-changed', handler)
  }, [loadLayout])

  if (loading) {
    return <div className="settings-hint">Загрузка...</div>
  }

  return (
    <div>
      <p className="settings-hint" style={{ marginBottom: '16px' }}>
        Перетащите виджет в левую или правую зону на главной странице.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {ALL_WIDGETS.map(id => {
          const leftIdx = layout.left.indexOf(id)
          const rightIdx = layout.right.indexOf(id)
          const isPlaced = leftIdx !== -1 || rightIdx !== -1
          const zone = leftIdx !== -1 ? 'left' : rightIdx !== -1 ? 'right' : null
          return (
            <DraggableWidgetCard
              key={id}
              id={id}
              isPlaced={isPlaced}
              zone={zone}
            />
          )
        })}
      </div>
    </div>
  )
}
