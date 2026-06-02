// Text emoji → Unicode emoji mapping
const EMOJI_MAP: Record<string, string> = {
  // Smiles
  ':)': '😊',
  ':-)': '😊',
  ':(': '😢',
  ':-(': '😢',
  ':D': '😄',
  ':-D': '😄',
  ';)': '😉',
  ';-)': '😉',
  ':P': '😛',
  ':-P': '😛',
  ':p': '😛',
  ':O': '😮',
  ':-O': '😮',
  ':o': '😮',
  ':|': '😐',
  ':-|': '😐',
  ':/': '😕',
  ':-/': '😕',
  ':\\': '😕',
  'B)': '😎',
  'B-)': '😎',
  '<3': '❤️',
  '</3': '💔',
  ':*': '😘',
  ':-*': '😘',
  ':@': '😠',
  ':-@': '😠',
  ':$': '😳',
  ':-$': '😳',
  '>:(': '😡',
  'D:': '😨',
  ':3': '😺',
  '^_^': '😊',
  'o_O': '😳',
  'O_o': '😳',
  'T_T': '😭',
  'T.T': '😭',
  '._.': '😐',
  '-_-': '😑',
  'xD': '😆',
  'XD': '😆',
  ':])': '😄',
  ':[': '😟',
}

// Sorted by length (longest first) to avoid partial replacements
const EMOJI_KEYS = Object.keys(EMOJI_MAP).sort((a, b) => b.length - a.length)

// Escape special regex chars in emoji keys
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Build regex pattern once
const EMOJI_REGEX = new RegExp(
  EMOJI_KEYS.map(escapeRegex).join('|'),
  'g'
)

export function convertTextEmojis(text: string): string {
  return text.replace(EMOJI_REGEX, (match) => EMOJI_MAP[match] || match)
}

// Popular emojis for the picker panel
export const POPULAR_EMOJIS = [
  // Faces
  '😊', '😂', '🥹', '😍', '🤩', '😎', '🤔', '😅', '😢', '😡',
  '🥺', '😱', '🤗', '😏', '😴', '🤮', '🥳', '😇', '🫠', '💀',
  // Gestures
  '👍', '👎', '👏', '🙌', '🤝', '✌️', '🤞', '💪', '🫡', '👋',
  // Hearts & symbols
  '❤️', '🔥', '⭐', '✨', '💡', '🎯', '🚀', '💯', '✅', '❌',
  // Objects
  '📌', '📝', '💻', '🎮', '🎵', '☕', '🍕', '🌟', '🌈', '⚡',
  // Animals
  '🐱', '🐶', '🦊', '🐼', '🐸', '🦋', '🐝', '🐢', '🦄', '🐧',
]
