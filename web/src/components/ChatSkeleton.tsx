/**
 * ChatSkeleton — shown while the chat's initial data is being resolved
 * (agent list, history fetch). Reserves the chat's layout space so the
 * real content swap doesn't shift the page.
 *
 * Shows a centered LoadingSpinner while loading.
 */
import { LoadingSpinner } from './LoadingSpinner'

export function ChatSkeleton() {
  return (
    <div className="chat-skeleton" aria-busy="true" aria-label="Загрузка чата">
      <div className="messages-area">
        <LoadingSpinner text="Загрузка чата..." />
      </div>
      <div className="bottom-input" />
    </div>
  )
}
