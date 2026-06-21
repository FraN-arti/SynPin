/**
 * ConnectionsCanvas — visual graph of inter-department connections.
 *
 * Uses React Flow for the canvas and ELK.js for auto-layout.
 * Shows department nodes with edges representing connections.
 * Real-time updates via WebSocket.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import ELK from 'elkjs/lib/elk.bundled.js'
import { API_BASE } from '../config'
import { LoadingSpinner } from './LoadingSpinner'

// ── Types ───────────────────────────────────────────────────────────────────

interface GraphNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: {
    name: string
    head: string
    level: number
    workers_count: number
    active_tasks: number
    status: string
  }
}

interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  label: string
  animated: boolean
  data: {
    connection_types: string[]
    color: string
    active_transfers: number
  }
}

interface Connection {
  id: string
  from: string
  to: string
  type: string
  label: string
  description: string
  active: boolean
}

// ── Department Node Component ───────────────────────────────────────────────

function DepartmentNode({ data }: { data: GraphNode['data'] }) {
  const statusColor = data.status === 'blocked' ? '#ef4444' : data.active_tasks > 0 ? '#f97316' : '#22c55e'

  return (
    <div className="connection-node">
      <Handle type="target" position={Position.Left} id="left" style={{ background: '#6b7280', width: 8, height: 8 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ background: '#6b7280', width: 8, height: 8 }} />
      <div className="connection-node-header">
        <span className="connection-node-dot" style={{ background: statusColor }} />
        <span className="connection-node-name">{data.name}</span>
      </div>
      <div className="connection-node-meta">
        {data.head && <span className="connection-node-head">Глава: {data.head}</span>}
        <span className="connection-node-workers">Worker'ов: {data.workers_count}</span>
      </div>
      {data.active_tasks > 0 && (
        <div className="connection-node-tasks">
          <span className="connection-node-task-badge">{data.active_tasks} {data.active_tasks === 1 ? 'задача' : data.active_tasks < 5 ? 'задачи' : 'задач'}</span>
        </div>
      )}
      <Handle type="source" position={Position.Right} id="right" style={{ background: '#6b7280', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ background: '#6b7280', width: 8, height: 8 }} />
    </div>
  )
}

const nodeTypes: NodeTypes = { department: DepartmentNode }

// ── ELK Layout ──────────────────────────────────────────────────────────────

const elk = new ELK()

async function layoutGraph(nodes: Node[], edges: Edge[]): Promise<Node[]> {
  if (nodes.length === 0) return nodes

  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '60',
      'elk.layered.spacing.nodeNodeBetweenLayers': '100',
      'elk.edgeRouting': 'ORTHOGONAL',
    },
    children: nodes.map(n => ({
      id: n.id,
      width: 200,
      height: 100,
    })),
    edges: edges.map(e => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  }

  try {
    const layouted = await elk.layout(graph)
    return nodes.map(node => {
      const layoutNode = layouted.children?.find(c => c.id === node.id)
      return {
        ...node,
        position: {
          x: layoutNode?.x ?? node.position.x,
          y: layoutNode?.y ?? node.position.y,
        },
      }
    })
  } catch (e) {
    console.error('[connections] ELK layout failed:', e)
    return nodes
  }
}

// ── Main Component ──────────────────────────────────────────────────────────

interface ConnectionsCanvasProps {
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export function ConnectionsCanvas({ wsOn }: ConnectionsCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string; connections: Connection[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [connections, setConnections] = useState<Connection[]>([])
  const [otdelNames, setOtdelNames] = useState<Record<string, string>>({})
  
  // Project filtering
  const [projects, setProjects] = useState<{id: string; name: string; departments: {id: string}[]}[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>('')
  const [allNodes, setAllNodes] = useState<Node[]>([])
  const [allEdges, setAllEdges] = useState<Edge[]>([])

  // Activity toast — shows when approval starts/completes
  const [activityToast, setActivityToast] = useState<{ message: string; type: 'start' | 'complete' } | null>(null)

  // Load graph data
  const loadGraph = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections/graph`)
      if (!res.ok) return
      const data = await res.json()

      const flowNodes: Node[] = data.nodes.map((n: GraphNode) => ({
        id: n.id,
        type: 'department',
        position: n.position,
        data: n.data,
      }))

      const flowEdges: Edge[] = data.edges.map((e: GraphEdge) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: 'right',
        targetHandle: 'left',
        type: 'step',
        animated: e.animated,
        label: e.label,
        style: { stroke: e.data?.color || '#6b7280', strokeWidth: 2 },
        labelStyle: { fill: '#fff', fontSize: 11, fontWeight: 600 },
        labelBgStyle: { fill: 'rgba(0,0,0,0.75)', stroke: e.data?.color || '#6b7280', strokeWidth: 1, borderRadius: 4 },
        labelBgPadding: [6, 4] as [number, number],
        data: { connectionTypes: e.data?.connection_types || [], activeTransfers: e.data?.active_transfers || 0 },
      }))

      console.log('[connections] setting nodes:', flowNodes.length, 'edges:', flowEdges.length)
      setAllNodes(flowNodes)
      setAllEdges(flowEdges)
      setNodes(flowNodes)
      setEdges(flowEdges)
    } catch (e) {
      console.error('[connections] load graph error:', e)
    } finally {
      setLoading(false)
    }
  }, [setNodes, setEdges])
  
  // Load projects for filtering
  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`)
      if (!res.ok) return
      const data = await res.json()
      setProjects(data.projects || [])
    } catch {}
  }, [])

  // Load connections list
  const loadConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections`)
      if (res.ok) {
        const data = await res.json()
        setConnections(data.connections || [])
      }
    } catch {}
  }, [])

  // Load otdel names for display
  const loadOtdelNames = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        const names: Record<string, string> = {}
        for (const o of (data.otdels || [])) {
          names[o.otdelid] = o.name
        }
        setOtdelNames(names)
      }
    } catch {}
  }, [])

  // Initial load
  useEffect(() => {
    loadGraph()
    loadConnections()
    loadOtdelNames()
    loadProjects()
  }, [loadGraph, loadConnections, loadOtdelNames, loadProjects])
  
  // Filter by project
  useEffect(() => {
    if (!selectedProjectId) {
      setNodes(allNodes)
      setEdges(allEdges)
      return
    }
    
    const project = projects.find(p => p.id === selectedProjectId)
    if (!project) return
    
    const deptIds = new Set(project.departments.map(d => d.id))
    const filteredNodes = allNodes.filter(n => deptIds.has(n.id))
    const filteredEdges = allEdges.filter(e => deptIds.has(e.source) && deptIds.has(e.target))
    
    setNodes(filteredNodes)
    setEdges(filteredEdges)
  }, [selectedProjectId, projects, allNodes, allEdges, setNodes, setEdges])

  // WebSocket live updates
  useEffect(() => {
    if (!wsOn) return
    const unsubs = [
      wsOn('connections:created', () => { loadGraph(); loadConnections() }),
      wsOn('connections:updated', () => { loadGraph(); loadConnections() }),
      wsOn('connections:deleted', () => { loadGraph(); loadConnections() }),
      wsOn('connections:approval_started', (data: any) => {
        loadGraph()
        const fromName = data?.approval?.from_name || data?.approval?.from || ''
        const toName = data?.approval?.to_name || data?.approval?.to || ''
        setActivityToast({ message: `Передача: ${fromName} → ${toName}`, type: 'start' })
        setTimeout(() => setActivityToast(null), 4000)
      }),
      wsOn('connections:approval_complete', () => {
        loadGraph()
        setActivityToast({ message: 'Передача завершена', type: 'complete' })
        setTimeout(() => setActivityToast(null), 3000)
      }),
      wsOn('connections:positions_updated', () => { loadGraph() }),
    ]
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadGraph, loadConnections, otdelNames])

  // Сравнять with ELK
  const handleAutoLayout = useCallback(async () => {
    const layouted = await layoutGraph(nodes, edges)
    setNodes(layouted)

    // Save positions
    const positions: Record<string, { x: number; y: number }> = {}
    layouted.forEach(n => { positions[n.id] = n.position })
    try {
      await fetch(`${API_BASE}/api/connections/positions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions }),
      })
    } catch {}
  }, [nodes, edges, setNodes])

  // Save positions on drag end
  const handleNodeDragStop = useCallback(async () => {
    const positions: Record<string, { x: number; y: number }> = {}
    nodes.forEach(n => { positions[n.id] = n.position })
    try {
      await fetch(`${API_BASE}/api/connections/positions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions }),
      })
    } catch {}
  }, [nodes])

  // Click on edge → show all connections between those departments
  const handleEdgeClick = useCallback((_: any, edge: Edge) => {
    const related = connections.filter(c =>
      (c.from === edge.source && c.to === edge.target) ||
      (c.from === edge.target && c.to === edge.source)
    )
    if (related.length > 0) {
      setSelectedEdge({ source: edge.source, target: edge.target, connections: related })
    }
  }, [connections])

  // Delete connection
  const handleDeleteConnection = useCallback(async (connId: string) => {
    if (!confirm('Удалить связь? Все связанные данные будут удалены.')) return
    try {
      await fetch(`${API_BASE}/api/connections/${connId}`, { method: 'DELETE' })
      // Refresh edge panel
      setSelectedEdge(prev => {
        if (!prev) return null
        const remaining = prev.connections.filter(c => c.id !== connId)
        return remaining.length > 0 ? { ...prev, connections: remaining } : null
      })
      loadConnections()
    } catch {}
  }, [loadConnections])

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", minHeight: "calc(100vh - 100px)" }}>
        <LoadingSpinner text="Загрузка графа..." />
      </div>
    )
  }

  return (
    <div className="connections-canvas-wrapper">
      <div className="connections-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={handleNodeDragStop}
          onEdgeClick={handleEdgeClick}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <Controls />
        </ReactFlow>

        {/* Activity toast — shows during active transfers */}
        {activityToast && (
          <div className={`connection-activity-toast ${activityToast.type}`}>
            <span className="connection-activity-dot" />
            {activityToast.message}
          </div>
        )}

        {/* Toolbar */}
        <div className="connections-toolbar">
          {/* Project filter */}
          {projects.length > 0 && (
            <select
              className="connections-project-filter"
              value={selectedProjectId}
              onChange={e => setSelectedProjectId(e.target.value)}
            >
              <option value="">Все проекты</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
          <button className="connections-toolbar-btn" onClick={handleAutoLayout}>
            Сравнять
          </button>
        </div>
      </div>

      {/* Properties panel */}
      {selectedEdge && (
        <div className="connections-panel">
          <div className="connections-panel-header">
            <h3>Связи</h3>
            <button className="modal-close" onClick={() => setSelectedEdge(null)}>×</button>
          </div>
          <div className="connections-panel-body">
            <div className="expanded-field">
              <label>Между отделами</label>
              <span style={{ fontWeight: 600 }}>
                {otdelNames[selectedEdge.source] || selectedEdge.source}
                {' → '}
                {otdelNames[selectedEdge.target] || selectedEdge.target}
              </span>
            </div>
            <div className="settings-divider-thin" />
            {selectedEdge.connections.map(conn => (
              <div key={conn.id} className="connection-detail-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span className="connection-type-badge" data-type={conn.type}>
                    {conn.type === 'peer' ? 'Равноправная' : conn.type === 'approval' ? 'Утверждение' : 'Делегирование'}
                  </span>
                  <span style={{ fontWeight: 600, color: 'var(--text)', fontSize: '13px' }}>
                    {conn.label || '—'}
                  </span>
                </div>
                {conn.description && (
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>{conn.description}</span>
                )}
                <button className="btn-action btn-action-delete" style={{ position: 'absolute', top: '8px', right: '8px' }}
                  onClick={() => handleDeleteConnection(conn.id)} title="Удалить">×</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
