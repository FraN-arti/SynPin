/**
 * ChatSkeleton — shown while the chat's initial data is being resolved
 * (agent list, history fetch). Reserves the chat's layout space so the
 * real content swap doesn't shift the page.
 *
 * Renders an empty <main> with the same structural blocks as the real
 * chat (messages-area, bottom-input) but no visible content. No
 * animation, no transform — instant mount, instant unmount.
 *
 * Why empty instead of placeholder "skeleton bones": the user is on a
 * dark glass theme; grey bars distract more than they help. The
 * moment data is ready the real content replaces this block, so the
 * user perceives a brief "loading" then the actual chat — better than
 * distracting with moving/shimmering shapes.
 */
export function ChatSkeleton() {
  return (
    <div className="chat-skeleton" aria-busy="true" aria-label="Загрузка чата">
      <div className="messages-area" />
      <div className="bottom-input" />
    </div>
  )
}
