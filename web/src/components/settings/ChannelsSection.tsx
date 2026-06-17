/**
 * Channels settings section + AddChannelModal.
 * Extracted from SettingsPage.tsx (lines 2262-2321, 2680-2743).
 */

import { useState } from 'react'
import { DropdownMenu as CustomDropdown } from '../DropdownMenu'
import { Toggle } from './Toggle'

const sampleChannels = [
  { id: 'feishu-main', name: 'Feishu — Основной', type: 'feishu', status: 'connected', binding: 'Основной агент', mode: 'websocket' },
  { id: 'whatsapp-board', name: 'WhatsApp — Совет директоров', type: 'whatsapp', status: 'disconnected', binding: 'Совет директоров', mode: 'webhook' },
  { id: 'telegram-qa', name: 'Telegram — QA команда', type: 'telegram', status: 'disconnected', binding: 'QA департамент', mode: 'polling' },
]

export function ChannelsSection({ onAddChannel }: { onAddChannel: () => void }) {
  const [channels] = useState(sampleChannels)
  const typeIcons: Record<string, string> = { feishu: '🟢', whatsapp: '💬', telegram: '✈️', slack: '💜', discord: '🎮', email: '📧' }

  return (
    <div className="settings-sections">
      <div className="section-header-row">
        <span className="section-count">{channels.filter(c => c.status === 'connected').length} подключено</span>
        <button className="settings-btn-primary" onClick={onAddChannel}>+ Добавить канал</button>
      </div>
      {channels.map(channel => (
        <div key={channel.id} className={`settings-card channel-card ${channel.status !== 'connected' ? 'disconnected' : ''}`}>
          <div className="channel-header">
            <div className="channel-identity">
              <span className="channel-icon">{typeIcons[channel.type] || '📡'}</span>
              <span className={`channel-status-dot ${channel.status}`} />
              <div>
                <span className="channel-name">{channel.name}</span>
                <span className="channel-meta">{channel.type} · {channel.mode} · {channel.binding}</span>
              </div>
            </div>
            <span className={`channel-status-badge ${channel.status}`}>
              {channel.status === 'connected' ? 'Подключён' : 'Отключён'}
            </span>
          </div>
          {channel.status === 'connected' && (
            <div className="channel-details">
              <div className="settings-field">
                <label>Привязка</label>
                <CustomDropdown
                  value="main"
                  onChange={() => {}}
                  options={[
                    { value: 'main', label: 'Основной агент' },
                    { value: 'department:dev', label: 'Отдел: Разработка' },
                    { value: 'department:qa', label: 'Отдел: QA' },
                    { value: 'agent:architect', label: 'Агент: Архитектор' },
                  ]}
                />
              </div>
              <Toggle label="Уведомления" defaultChecked />
              <Toggle label="Загрузка файлов" defaultChecked />
              <Toggle label="Слэш-команды" defaultChecked />
              <div className="provider-actions">
                <button className="settings-btn-secondary">Сохранить</button>
                <button className="settings-btn-danger">Отключить</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export function AddChannelModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-inner">
      <h2 className="modal-title">Добавить канал связи</h2>
      <div className="modal-body">
        <div className="settings-field">
          <label>Название</label>
          <input type="text" className="settings-input" placeholder="Feishu — Основной" />
        </div>
        <div className="settings-field">
          <label>Тип канала</label>
          <CustomDropdown
            value="feishu"
            onChange={() => {}}
            options={[
              { value: 'feishu', label: '🟢 Feishu (Lark)' },
              { value: 'whatsapp', label: '💬 WhatsApp Business' },
              { value: 'telegram', label: '✈️ Telegram' },
              { value: 'slack', label: '💜 Slack' },
              { value: 'discord', label: '🎮 Discord' },
              { value: 'email', label: '📧 Email' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>Режим подключения</label>
          <CustomDropdown
            value="websocket"
            onChange={() => {}}
            options={[
              { value: 'websocket', label: 'WebSocket' },
              { value: 'webhook', label: 'Webhook' },
              { value: 'polling', label: 'Polling' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>Привязка к</label>
          <CustomDropdown
            value="main"
            onChange={() => {}}
            options={[
              { value: 'main', label: 'Основной агент' },
              { value: 'department', label: 'Отдел' },
              { value: 'agent', label: 'Конкретный агент' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>App ID</label>
          <input type="text" className="settings-input" placeholder="cli_a5..." />
        </div>
        <div className="settings-field">
          <label>App Secret</label>
          <input type="password" className="settings-input" placeholder="***" />
        </div>
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={onClose}>Сохранить</button>
      </div>
    </div>
  )
}
