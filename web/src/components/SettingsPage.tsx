/**
 * SettingsPage — tab-based settings shell.
 *
 * Sections extracted to settings/ directory:
 *   - GeneralSection, AgentsSection, ProvidersSection,
 *     ChannelsSection, DepartmentsSection, SkillsSection, KanbanSection
 *
 * This file is the orchestrator: tab nav, modals, routing.
 */

import { useState, useRef, useEffect } from 'react'
import { PROVIDER_CATALOG, providerKey, type ProviderInfo } from '../lib/providers'
import { MemorySection } from './MemorySection'
import { type DropdownOption } from './DropdownMenu'
import { useDraggable } from '@dnd-kit/core'
import { PageTransition } from './PageTransition'

// ── Section imports ────────────────────────────────────────────────
import { SYSTEM_TABS, SPACE_TABS, SECTION_INFO, DRAGGABLE_TABS, type Tab } from './settings/types'
import type { ApiProvider } from './settings/types'
import { GeneralSection } from './settings/GeneralSection'
import { AgentsSection } from './settings/AgentsSection'
import { ProvidersSection, AddFromCatalogModal, AddProviderModal, EditCustomProviderModal } from './settings/ProvidersSection'
import { ChannelsSection, AddChannelModal } from './settings/ChannelsSection'
import { DepartmentsSection } from './settings/DepartmentsSection'
import { SkillsSection } from './settings/SkillsSection'
import { ConnectionsSection } from './settings/ConnectionsSection'
import { KanbanSection } from './settings/KanbanSection'
import { DeadlinesSection } from './settings/DeadlinesSection'
import { ProjectsSection } from './settings/ProjectsSection'
import { WidgetsSection } from './settings/WidgetsSection'

// ── Re-exports for backward compatibility ──────────────────────────
export type { DropdownOption }

// ── DraggableTab ───────────────────────────────────────────────────

function DraggableTab({ tab, isActive, onClick }: { tab: { id: string; label: string }; isActive: boolean; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `tab-${tab.id}`,
    data: { type: tab.id, source: 'settings-tab' },
  })

  const isDraggable = DRAGGABLE_TABS.has(tab.id)

  return (
    <button
      ref={isDraggable ? setNodeRef : undefined}
      className={`settings-nav-tab ${isActive ? 'active' : ''} ${isDraggable ? 'draggable' : ''} ${isDragging ? 'dragging' : ''}`}
      onClick={onClick}
      {...(isDraggable ? { ...attributes, ...listeners } : {})}
      title={isDraggable ? 'Перетащить на панель виджетов' : undefined}
    >
      {tab.label}
    </button>
  )
}

// ── SettingsPage (main export) ─────────────────────────────────────

interface SettingsPageProps {
  onAgentsChange?: () => void
  onDepartmentsChange?: () => void
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export function SettingsPage({ onAgentsChange, onDepartmentsChange, wsOn }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<Tab>('general')
  const [activeModal, setActiveModal] = useState<string | null>(null)
  const [addingProvider, setAddingProvider] = useState<ProviderInfo | null>(null)
  const [editingProvider, setEditingProvider] = useState<ApiProvider | null>(null)
  const providersRef = useRef<{ refresh: () => void }>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => { requestAnimationFrame(() => setVisible(true)) }, [])

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab)
  }

  return (
    <>
      {/* Modal overlay */}
      {activeModal && (
        <div className="modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            {activeModal === 'add-provider-openai' && <AddProviderModal type="openai" onClose={() => setActiveModal(null)} onSaved={() => { setActiveModal(null); providersRef.current?.refresh() }} />}
            {activeModal === 'add-provider-anthropic' && <AddProviderModal type="anthropic" onClose={() => setActiveModal(null)} onSaved={() => { setActiveModal(null); providersRef.current?.refresh() }} />}
            {activeModal === 'add-channel' && <AddChannelModal onClose={() => setActiveModal(null)} />}
          </div>
        </div>
      )}

      {/* Add from catalog modal */}
      {addingProvider && (
        <div className="modal-overlay" onClick={() => setAddingProvider(null)}>
          <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
            <AddFromCatalogModal
              provider={addingProvider}
              onClose={() => setAddingProvider(null)}
              onSaved={() => { setAddingProvider(null); providersRef.current?.refresh() }}
            />
          </div>
        </div>
      )}

      {/* Edit provider modal */}
      {editingProvider && (() => {
        const catalogEntry = PROVIDER_CATALOG.find(p => providerKey(p) === editingProvider.name)
        if (catalogEntry) {
          return (
            <div className="modal-overlay" onClick={() => setEditingProvider(null)}>
              <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
                <AddFromCatalogModal
                  provider={catalogEntry}
                  editProvider={editingProvider}
                  onClose={() => setEditingProvider(null)}
                  onSaved={() => { setEditingProvider(null); providersRef.current?.refresh() }}
                />
              </div>
            </div>
          )
        }
        return (
          <div className="modal-overlay" onClick={() => setEditingProvider(null)}>
            <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
              <EditCustomProviderModal
                provider={editingProvider}
                onClose={() => setEditingProvider(null)}
                onSaved={() => { setEditingProvider(null); providersRef.current?.refresh() }}
              />
            </div>
          </div>
        )
      })()}

      <div className={`settings-page ${visible ? "visible" : ""}`}>
        {/* Header */}
        <div className="settings-top-bar">
          <div className="settings-section-header">
            <h1 className="settings-section-title">{SECTION_INFO[activeTab].title}</h1>
            <p className="settings-section-desc">{SECTION_INFO[activeTab].description}</p>
          </div>
        </div>

        {/* Horizontal tab navigation */}
        <nav className="settings-nav-tabs">
          <div className="settings-nav-group">
            <span className="settings-nav-group-label">Система</span>
            <div className="settings-nav-group-items">
              {SYSTEM_TABS.map(tab => (
                <DraggableTab
                  key={tab.id}
                  tab={tab}
                  isActive={activeTab === tab.id}
                  onClick={() => handleTabChange(tab.id)}
                />
              ))}
            </div>
          </div>
          <div className="settings-nav-group">
            <span className="settings-nav-group-label">Пространство</span>
            <div className="settings-nav-group-items">
              {SPACE_TABS.map(tab => (
                <DraggableTab
                  key={tab.id}
                  tab={tab}
                  isActive={activeTab === tab.id}
                  onClick={() => handleTabChange(tab.id)}
                />
              ))}
            </div>
          </div>
          <div className="settings-nav-group">
            <span className="settings-nav-group-label">Разработка</span>
            <div className="settings-nav-group-items">
              <DraggableTab
                tab={{ id: 'projects' as Tab, label: 'Проекты' }}
                isActive={activeTab === 'projects'}
                onClick={() => handleTabChange('projects')}
              />
              <DraggableTab
                tab={{ id: 'deadlines' as Tab, label: 'Дедлайны' }}
                isActive={activeTab === 'deadlines'}
                onClick={() => handleTabChange('deadlines')}
              />
              <DraggableTab
                tab={{ id: 'kanban' as Tab, label: 'Канбан' }}
                isActive={activeTab === 'kanban'}
                onClick={() => handleTabChange('kanban')}
              />
            </div>
          </div>
        </nav>

        {/* Tab content */}
        <PageTransition pageKey={activeTab}>
          {activeTab === 'general' && <GeneralSection />}
          {activeTab === 'agents' && <AgentsSection onAgentsChange={onAgentsChange} wsOn={wsOn} />}
          {activeTab === 'providers' && (
            <ProvidersSection
              ref={providersRef}
              onAddProvider={type => setActiveModal(`add-provider-${type}`)}
              onAddFromCatalog={p => setAddingProvider(p)}
              onEditProvider={p => setEditingProvider(p)}
            />
          )}
          {activeTab === 'memory' && <MemorySection />}
          {activeTab === 'channels' && <ChannelsSection onAddChannel={() => setActiveModal('add-channel')} />}
          {activeTab === 'departments' && <DepartmentsSection onDepartmentsChange={onDepartmentsChange} />}
          {activeTab === 'skills' && <SkillsSection />}
          {activeTab === 'connections' && <ConnectionsSection wsOn={wsOn} />}
          {activeTab === 'kanban' && <KanbanSection />}
          {activeTab === 'projects' && <ProjectsSection />}
          {activeTab === 'deadlines' && <DeadlinesSection />}
          {activeTab === 'widgets' && <WidgetsSection />}
        </PageTransition>
      </div>
    </>
  )
}
