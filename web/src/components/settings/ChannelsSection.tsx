/**
 * Channels settings section + AddChannelModal.
 * Extracted from SettingsPage.tsx (lines 2262-2321, 2680-2743).
 */

import { DropdownMenu as CustomDropdown } from '../DropdownMenu'
import { Toggle } from './Toggle'

const sampleChannels = [
  { id: 'feishu-main', name: 'Feishu — Основной', type: 'feishu', status: 'connected', binding: 'Основной агент', mode: 'websocket' },
  { id: 'whatsapp-board', name: 'WhatsApp — Совет директоров', type: 'whatsapp', status: 'disconnected', binding: 'Совет директоров', mode: 'webhook' },
  { id: 'telegram-qa', name: 'Telegram — QA команда', type: 'telegram', status: 'disconnected', binding: 'QA департамент', mode: 'polling' },
]

/**
 * Channels settings section — в разработке.
 * Ранее содержал моковые данные (sampleChannels) без реальной функциональности.
 * Пока не реализован — показываем заглушку.
 */

export function ChannelsSection({ onAddChannel }: { onAddChannel: () => void }) {
  return (
    <div className="settings-sections">
      <div className="settings-card" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 8 }}>
          Каналы связи (Telegram, WhatsApp, Feishu, Discord) — в разработке.
        </p>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, opacity: 0.7 }}>
          Подключение мессенджеров будет доступно в следующих версиях.
        </p>
      </div>
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
