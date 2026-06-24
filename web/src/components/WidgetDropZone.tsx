import { useState, useCallback, useEffect } from 'react'
import {
  useDroppable,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { KanbanWidget } from './KanbanWidget'

// ─── Types ───────────────────────────────────────────────────────

export type WidgetType = 'otdels' | 'kanban'

export interface WidgetLayout {
  left: WidgetType[]
  right: WidgetType[]
}

export interface Department {
  id: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
  head: string
  workers: string[]
}

// ─── Widget metadata ─────────────────────────────────────────────

export const WIDGET_META: Record<WidgetType, { label: string; icon: string }> = {
  otdels: { label: 'Отделы', icon: '🏢' },
  kanban: { label: 'Канбан', icon: '📋' },
}

// ─── Layout persistence ──────────────────────────────────────────

import { API_BASE } from '../config'

const STORAGE_KEY = 'synpin_widget_layout'
const EMPTY_LAYOUT: WidgetLayout = { left: [], right: [] }

/** Migrate old localStorage layout to backend, then clear localStorage. */
async function migrateLocalStorageIfNeeded(): Promise<WidgetLayout | null> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const migrate = (arr: string[]) =>
          (arr || []).map((w: string) => w === 'departments' ? 'otdels' : w)
          .filter((w: string) => ['otdels', 'kanban'].includes(w)) as WidgetType[]
    let layout: WidgetLayout
    if (parsed.widgets && Array.isArray(parsed.widgets)) {
      layout = { left: migrate(parsed.widgets), right: [] }
    } else {
      layout = { left: migrate(parsed.left), right: migrate(parsed.right) }
    }
    // Save to backend and clear localStorage
    await saveWidgetLayout(layout)
    localStorage.removeItem(STORAGE_KEY)
    return layout
  } catch {
    return null
  }
}

export async function loadWidgetLayout(): Promise<WidgetLayout> {
  try {
    // Try backend first
    const res = await fetch(`${API_BASE}/api/widgets/layout`)
    if (res.ok) {
      const data = await res.json()
      return {
        left: (data.left || []).filter((w: string) => ['otdels', 'kanban'].includes(w)),
        right: (data.right || []).filter((w: string) => ['otdels', 'kanban'].includes(w)),
      }
    }
  } catch {}
  // Fallback: migrate from localStorage
  const migrated = await migrateLocalStorageIfNeeded()
  if (migrated) return migrated
  return EMPTY_LAYOUT
}

export async function saveWidgetLayout(layout: WidgetLayout): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/widgets/layout`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(layout),
    })
  } catch (e) {
    console.error('[widgets] save layout error:', e)
  }
}

// ─── Widget content renderers ────────────────────────────────────

function DepartmentsWidgetContent({ departments, onDepartmentClick, activeOtdelId }: { departments: Department[]; onDepartmentClick?: (id: string) => void; activeOtdelId?: string | null }) {
  if (departments.length === 0) {
    return <div className="widget-empty">Нет отделов</div>
  }
  return (
    <div className="widget-departments-list">
      {departments.map(dept => (
        <button key={dept.id} className={`sidebar-department-item ${dept.id === activeOtdelId ? 'active' : ''}`} onClick={() => onDepartmentClick?.(dept.id)}>
          <span className="department-color-dot" style={{ background: dept.color }} />
          <span className="sidebar-department-name">{dept.name}</span>
          <span className="sidebar-department-count">{dept.agent_count}</span>
        </button>
      ))}
    </div>
  )
}

// ─── Sortable widget card ────────────────────────────────────────

interface SortableWidgetProps {
  id: WidgetType
  departments: Department[]
  onRemove: (id: WidgetType) => void
  onDepartmentClick?: (id: string) => void
  activeOtdelId?: string | null
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

function SortableWidget({ id, departments, onRemove, onDepartmentClick, activeOtdelId, wsOn }: SortableWidgetProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  const meta = WIDGET_META[id as WidgetType] || { label: id, icon: '📦' }

  return (
    <div ref={setNodeRef} style={style} className={`widget-card ${isDragging ? 'dragging' : ''}`}>
      <div className="widget-card-header">
        <div className="widget-drag-handle" {...attributes} {...listeners}>
          <span className="widget-grip">⠿</span>
        </div>
        <span className="widget-icon">{meta.icon}</span>
        <span className="widget-title">{meta.label}</span>
        <button className="widget-remove-btn" onClick={() => onRemove(id)} title="Удалить из панели">
          ×
        </button>
      </div>
      <div className="widget-card-body">
        {id === 'otdels' && <DepartmentsWidgetContent departments={departments} onDepartmentClick={onDepartmentClick} activeOtdelId={activeOtdelId} />}
        {id === 'kanban' && <KanbanWidget wsOn={wsOn} />}
      </div>
    </div>
  )
}

// ─── Drop Zone ───────────────────────────────────────────────────

interface WidgetDropZoneProps {
  side: 'left' | 'right'
  widgets: WidgetType[]
  departments: Department[]
  onRemove: (side: 'left' | 'right', id: WidgetType) => void
  isDragging: boolean
  onDepartmentClick?: (id: string) => void
  activeOtdelId?: string | null
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export function WidgetDropZone({ side, widgets, departments, onRemove, isDragging, onDepartmentClick, activeOtdelId, wsOn }: WidgetDropZoneProps) {
  const { isOver, setNodeRef } = useDroppable({ id: `drop-zone-${side}` })

  // Show zone when dragging OR when has widgets
  if (widgets.length === 0 && !isDragging) return null

  // Unified visual: dashed border when dragging, glow when hovering
  const isDropTarget = isDragging && !isOver
  const isDropHover = isDragging && isOver

  return (
    <div
      ref={setNodeRef}
      className={[
        'widget-drop-zone', side,
        isDropHover ? 'drop-hover' : '',
        isDropTarget ? 'empty-drag-target' : '',
      ].filter(Boolean).join(' ')}
    >
      {isDropTarget && (
        <div className="drop-zone-placeholder">
          {side === 'left' ? '←' : '→'} Перетащите сюда
        </div>
      )}
      <SortableContext items={widgets} strategy={verticalListSortingStrategy}>
        <div className="widget-list">
          {widgets.map(widgetId => (
            <SortableWidget
              key={widgetId}
              id={widgetId}
              departments={departments}
              onRemove={(id) => onRemove(side, id)}
              onDepartmentClick={onDepartmentClick}
              activeOtdelId={activeOtdelId}
              wsOn={wsOn}
            />
          ))}
        </div>
      </SortableContext>
    </div>
  )
}

// ─── Layout Hook ─────────────────────────────────────────────────

export function useWidgetLayout(wsOn?: (type: string, handler: (data: any) => void) => () => void) {
  const [layout, setLayout] = useState<WidgetLayout>(EMPTY_LAYOUT)

  // Load layout from backend on mount
  useEffect(() => {
    loadWidgetLayout().then(setLayout)
  }, [])

  // Listen for WS layout changes from other clients
  useEffect(() => {
    if (!wsOn) return
    const off = wsOn('widgets:layout_changed', (msg: any) => {
      if (msg.layout) {
        setLayout(msg.layout)
      }
    })
    return off
  }, [wsOn])

  const syncLayout = useCallback((next: WidgetLayout) => {
    setLayout(next)
    saveWidgetLayout(next)
    window.dispatchEvent(new Event('synpin-widgets-changed'))
  }, [])

  const removeWidget = useCallback((side: 'left' | 'right', id: WidgetType) => {
    setLayout(prev => {
      const next = {
        ...prev,
        [side]: prev[side].filter(w => w !== id),
      }
      saveWidgetLayout(next)
      return next
    })
    window.dispatchEvent(new Event('synpin-widgets-changed'))
  }, [])

  const handleDragEnd = useCallback((event: { active: { id: string | number }; over: { id: string | number } | null } | null, activeLayout: WidgetLayout) => {
    if (!event || !event.over) return
    const { active, over } = event
    const widgetId = String(active.id)

    // New tab from settings — strip "tab-" prefix, or "lib-" from library
    const raw0 = widgetId.startsWith('tab-') ? widgetId.replace('tab-', '') : widgetId
    const raw = raw0.startsWith('lib-') ? raw0.replace('lib-', '') : raw0
    const widgetType = raw === 'departments' ? 'otdels' : raw
    if (!['otdels', 'kanban'].includes(widgetType)) return

    const overId = String(over.id)

    // Drop onto a zone
    if (overId === 'drop-zone-left' || overId === 'drop-zone-right') {
      const targetSide = overId === 'drop-zone-left' ? 'left' as const : 'right' as const
      const fromSide = activeLayout.left.includes(widgetType as WidgetType) ? 'left' as const
        : activeLayout.right.includes(widgetType as WidgetType) ? 'right' as const : null

      if (fromSide === targetSide && fromSide !== null) return
      if (fromSide) {
        syncLayout({
          ...activeLayout,
          [fromSide]: activeLayout[fromSide].filter(w => w !== widgetType),
          [targetSide]: [...activeLayout[targetSide], widgetType as WidgetType],
        })
      } else {
        // New widget from settings tab
        if (activeLayout.left.includes(widgetType as WidgetType) || activeLayout.right.includes(widgetType as WidgetType)) return
        syncLayout({
          ...activeLayout,
          [targetSide]: [...activeLayout[targetSide], widgetType as WidgetType],
        })
      }
      return
    }

    // Reorder within zone
    const leftIdx = activeLayout.left.indexOf(widgetType as WidgetType)
    const rightIdx = activeLayout.right.indexOf(widgetType as WidgetType)
    const overWidgetType = String(over.id)

    if (leftIdx !== -1) {
      const overIdx = activeLayout.left.indexOf(overWidgetType as WidgetType)
      if (overIdx !== -1 && leftIdx !== overIdx) {
        syncLayout({
          ...activeLayout,
          left: arrayMove(activeLayout.left, leftIdx, overIdx),
        })
      }
    } else if (rightIdx !== -1) {
      const overIdx = activeLayout.right.indexOf(overWidgetType as WidgetType)
      if (overIdx !== -1 && rightIdx !== overIdx) {
        syncLayout({
          ...activeLayout,
          right: arrayMove(activeLayout.right, rightIdx, overIdx),
        })
      }
    }
  }, [syncLayout])

  return { layout, removeWidget, handleDragEnd }
}
