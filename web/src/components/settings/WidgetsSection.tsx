/**
 * WidgetsSection — library of available widgets.
 * Cards are draggable into left/right panel zones via @dnd-kit.
 * Syncs with backend via WebSocket only (no redundant fetch on DOM event).
 */
import { useState, useEffect } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { API_BASE } from '../../config'
import { LoadingSpinner } from '../LoadingSpinner'
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

  // Initial load
  useEffect(() => {
    fetch(`${API_BASE}/api/widgets/layout`)
      .then(r => r.ok ? r.json() : { left: [], right: [] })
      .then(data => setLayout({ left: data.left || [], right: data.right || [] }))
      .catch((e) => console.error('[widgets] load widgets failed:', e))
      .finally(() => setLoading(false))
  }, [])

  // WS sync — single source of truth for layout updates
  useEffect(() => {
    if (!wsOn) {
      console.log('[widgets-section] no wsOn provided')
      return
    }
    console.log('[widgets-section] subscribing to widgets:layout_changed')
    const off = wsOn('widgets:layout_changed', (msg: any) => {
      if (msg.layout) {
        setLayout(msg.layout)
      }
    })
    return off
  }, [wsOn])

  if (loading) {
    return <LoadingSpinner text="Загрузка..." minHeight={80} />
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
