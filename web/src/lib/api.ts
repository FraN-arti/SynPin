/**
 * Centralized API client — single source of truth for all REST calls.
 *
 * Before this file, 106 fetch() calls were scattered across 7 components,
 * each duplicating `${API_BASE}/api/...` and error handling. This module
 * provides typed functions grouped by domain. Components import what they
 * need and call a clean function — no fetch boilerplate.
 *
 * Usage:
 *   import { api } from '../lib/api'
 *   const agents = await api.agents.list()
 *   await api.agents.create({ name: 'Nova', ... })
 */

import { API_BASE } from '../config'

// ── Generic helpers ────────────────────────────────────────────────

async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${options.method || 'GET'} ${path} → ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

function get<T = unknown>(path: string): Promise<T> {
  return request<T>(path)
}

function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
}

function put<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
}

function patch<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
}

function del<T = unknown>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

// ── API namespaces ─────────────────────────────────────────────────

export const api = {
  // ── Version ──────────────────────────────────────────────────
  version: {
    get: () => get<{ version: string; build?: string }>('/api/version'),
  },

  // ── Agents ───────────────────────────────────────────────────
  agents: {
    list: () => get<{ agents: unknown[] }>('/api/agents'),
    get: (slug: string) => get<unknown>(`/api/agents/${slug}`),
    create: (data: Record<string, unknown>) => post('/api/agents', data),
    update: (slug: string, data: Record<string, unknown>) =>
      patch(`/api/agents/${slug}`, data),
    delete: (slug: string) => del(`/api/agents/${slug}`),
  },

  // ── External agents ──────────────────────────────────────────
  externalAgents: {
    list: () => get<{ agents: unknown[] }>('/api/external-agents'),
    detect: () => get<unknown>('/api/external-agents/detect'),
    get: (slug: string) => get<unknown>(`/api/external-agents/${slug}`),
    create: (data: Record<string, unknown>) =>
      post('/api/external-agents', data),
    update: (slug: string, data: Record<string, unknown>) =>
      patch(`/api/external-agents/${slug}`, data),
    delete: (slug: string) => del(`/api/external-agents/${slug}`),
  },

  // ── Departments ──────────────────────────────────────────────
  departments: {
    list: () => get<{ departments: unknown[] }>('/api/departments'),
    create: (data: Record<string, unknown>) => post('/api/departments', data),
    update: (id: string, data: Record<string, unknown>) =>
      patch(`/api/departments/${id}`, data),
    delete: (id: string) => del(`/api/departments/${id}`),
  },

  // ── Roles ────────────────────────────────────────────────────
  roles: {
    list: () => get<{ roles: unknown[] }>('/api/roles'),
    create: (data: Record<string, unknown>) => post('/api/roles', data),
    update: (id: string, data: Record<string, unknown>) =>
      patch(`/api/roles/${id}`, data),
    delete: (id: string) => del(`/api/roles/${id}`),
  },

  // ── Otdels ───────────────────────────────────────────────────
  otdels: {
    list: () => get<{ otdels: unknown[] }>('/api/otdels'),
    get: (id: string) => get<unknown>(`/api/otdels/${id}`),
    create: (data: Record<string, unknown>) => post('/api/otdels', data),
    update: (id: string, data: Record<string, unknown>) =>
      patch(`/api/otdels/${id}`, data),
    delete: (id: string) => del(`/api/otdels/${id}`),
    chatHistory: (id: string) =>
      get<{ messages: unknown[] }>(`/api/otdels/${id}/chat/history`),
  },

  // ── Providers ────────────────────────────────────────────────
  providers: {
    list: () => get<{ providers: unknown[] }>('/api/providers'),
    create: (data: Record<string, unknown>) => post('/api/providers', data),
    update: (name: string, data: Record<string, unknown>) =>
      patch(`/api/providers/${encodeURIComponent(name)}`, data),
    delete: (name: string) =>
      del(`/api/providers/${encodeURIComponent(name)}`),
    test: (name: string) =>
      post<unknown>(`/api/providers/${encodeURIComponent(name)}/test`),
    fetchModels: (name: string, baseUrl: string, type: string, apiKey: string) =>
      get<unknown>(
        `/api/providers/${encodeURIComponent(name)}/models?base_url=${encodeURIComponent(baseUrl)}&type=${encodeURIComponent(type)}&api_key=${encodeURIComponent(apiKey)}`,
      ),
  },

  // ── Config ───────────────────────────────────────────────────
  config: {
    getSettings: () => get<Record<string, unknown>>('/api/config/settings'),
    updateSettings: (data: Record<string, unknown>) =>
      patch('/api/config/settings', data),
    getPrimaryAgent: () =>
      get<{ agent_slug: string }>('/api/config/primary-agent'),
    setPrimaryAgent: (slug: string) =>
      put('/api/config/primary-agent', { agent_slug: slug }),
    getMemory: () => get<Record<string, unknown>>('/api/config/memory'),
    updateMemory: (data: Record<string, unknown>) =>
      put('/api/config/memory', data),
  },

  // ── Memory ───────────────────────────────────────────────────
  memory: {
    getUser: () => get<{ entries: unknown[] }>('/api/memory/user'),
  },

  // ── Tools ────────────────────────────────────────────────────
  tools: {
    list: () => get<{ tools: unknown[] }>('/api/tools'),
    updateForAgent: (agentId: string, data: Record<string, unknown>) =>
      put(`/api/tools/${agentId}`, data),
  },

  // ── Stats ────────────────────────────────────────────────────
  stats: {
    overview: () => get<unknown>('/api/stats/overview'),
  },

  // ── Kanban ───────────────────────────────────────────────────
  kanban: {
    tasks: {
      board: () => get<unknown>('/api/kanban/tasks/board'),
      get: (id: string) => get<unknown>(`/api/kanban/tasks/${id}`),
      create: (data: Record<string, unknown>) =>
        post('/api/kanban/tasks', data),
      update: (id: string, data: Record<string, unknown>) =>
        patch(`/api/kanban/tasks/${id}`, data),
      delete: (id: string) => del(`/api/kanban/tasks/${id}`),
    },
    config: {
      getColumns: () => get<unknown>('/api/kanban/config/columns'),
      createColumn: (data: Record<string, unknown>) =>
        post('/api/kanban/config/columns', data),
      updateColumn: (id: string, data: Record<string, unknown>) =>
        patch(`/api/kanban/config/columns/${id}`, data),
      deleteColumn: (id: string) =>
        del(`/api/kanban/config/columns/${id}`),
      reorderColumns: (data: Record<string, unknown>) =>
        put('/api/kanban/config/columns', data),
      getLabels: () => get<unknown>('/api/kanban/config/labels'),
      createLabel: (data: Record<string, unknown>) =>
        post('/api/kanban/config/labels', data),
      updateLabel: (id: string, data: Record<string, unknown>) =>
        patch(`/api/kanban/config/labels/${id}`, data),
      deleteLabel: (id: string) =>
        del(`/api/kanban/config/labels/${id}`),
      getWidget: () => get<unknown>('/api/kanban/config/widget'),
      updateWidget: (data: Record<string, unknown>) =>
        put('/api/kanban/config/widget', data),
      getSettings: () => get<unknown>('/api/kanban/config/settings'),
      updateSettings: (data: Record<string, unknown>) =>
        put('/api/kanban/config/settings', data),
    },
    stats: () => get<unknown>('/api/kanban/stats'),
  },

  // ── Themes ───────────────────────────────────────────────────
  themes: {
    list: () => get<{ themes: unknown[] }>('/api/themes/tweakcn/list'),
    import: (data: Record<string, unknown>) =>
      post('/api/themes/tweakcn/import', data),
    save: (data: Record<string, unknown>) =>
      post('/api/themes/tweakcn/save', data),
  },

  // ── Chat (hermes) ────────────────────────────────────────────
  chat: {
    history: (agentSlug: string, channelId = 'web') =>
      get<{ messages: unknown[] }>(
        `/api/chat/history?agent_slug=${encodeURIComponent(agentSlug)}&channel_id=${encodeURIComponent(channelId)}`,
      ),
    stream: (data: Record<string, unknown>) =>
      fetch(`${API_BASE}/api/chat/hermes/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }),
  },
}

export type ApiClient = typeof api
