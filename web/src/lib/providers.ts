// Provider catalog — all supported LLM providers
// Auth methods synced from 9router (src/shared/constants/providers.js)

export interface ProviderInfo {
  id: string
  name: string
  key?: string  // YAML key (slug). If not set, derived from name
  iconFile?: string  // PNG filename in /providers/ (without extension)
  type: 'openai' | 'openai-compatible' | 'anthropic'
  category: 'oauth' | 'free-tier' | 'api-key'
  authMethod: 'oauth' | 'apikey' | 'no-auth'  // how auth works
  oauthDisabled?: boolean  // true = OAuth not yet implemented, show dimmed
  baseUrl: string
  defaultModels?: string[]  // pre-filled models (empty for providers that fetch dynamically)
  availableModels?: string[]  // models for clickable chips
  description?: string
  apiKeyHint?: string  // placeholder hint for API key field (e.g. "sk-...")
}

/** Get the YAML key (slug) for a catalog provider */
export function providerKey(p: ProviderInfo): string {
  return p.key || p.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
}

/** Get icon URL for a provider — returns path to /providers/{icon}.png or null */
export function providerIconUrl(p: ProviderInfo): string | null {
  const file = p.iconFile || providerKey(p)
  return `/providers/${file}.png`
}

export const PROVIDER_CATALOG: ProviderInfo[] = [
  // ─── Connected by default ─────────────────────────────────
  { id: '9router', name: '9Router', key: '9router', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'http://localhost:20128/v1', defaultModels: ['general-agent'], apiKeyHint: '9router-...' },

  // ─── OAuth Providers (NOT YET IMPLEMENTED — dimmed) ───────
  // 9router uses OAuth PKCE flow with loopback server for these.
  // We show them dimmed with "OAuth скоро" until the flow is built.
  { id: 'claude-code', name: 'Claude Code', key: 'claude-code', iconFile: 'claude', type: 'anthropic', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.anthropic.com', defaultModels: ['claude-sonnet-4', 'claude-opus-4'] },
  { id: 'cursor', name: 'Cursor IDE', key: 'cursor', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.cursor.sh', defaultModels: ['claude-3.5-sonnet', 'gpt-4o'] },
  { id: 'github-copilot', name: 'GitHub Copilot', key: 'github-copilot', iconFile: 'copilot', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.githubcopilot.com', defaultModels: ['gpt-4o', 'claude-3.5-sonnet'] },
  { id: 'cline', name: 'Cline', key: 'cline', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o', 'claude-sonnet-4'] },
  { id: 'kilo-code', name: 'Kilo Code', key: 'kilo-code', iconFile: 'kilocode', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o'] },
  { id: 'openai-codex', name: 'OpenAI Codex', key: 'openai-codex', iconFile: 'codex', type: 'openai', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.openai.com', defaultModels: ['o1', 'o1-mini', 'gpt-4o'] },
  { id: 'xAI-grok', name: 'xAI (Grok)', key: 'xai-grok', iconFile: 'xai', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.x.ai/v1', defaultModels: ['grok-2', 'grok-2-vision'] },
  { id: 'antigravity', name: 'Antigravity', key: 'antigravity', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o'] },

  // ─── OAuth (discontinued / deprecated by provider) ────────
  // These used OAuth in 9router but are now deprecated or discontinued.
  // Kept as dimmed OAuth entries so users know they exist but can't connect yet.
  { id: 'kiro-ai', name: 'Kiro AI', key: 'kiro-ai', iconFile: 'kiro', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://kiro.amazon.com', defaultModels: ['claude-sonnet-4.5', 'glm-5', 'minimax-m2.5'], description: 'OAuth через AWS Builder ID / Google / GitHub' },
  { id: 'qoder', name: 'Qoder', key: 'qoder', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://api.qoder.com', defaultModels: ['qoder-v1'], description: 'OAuth discontinued Alibaba (2026-04-15)' },
  { id: 'gemini-cli', name: 'Gemini CLI', key: 'gemini-cli', iconFile: 'gemini', type: 'openai-compatible', category: 'oauth', authMethod: 'oauth', oauthDisabled: true, baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', defaultModels: ['gemini-2.0-flash', 'gemini-2.5-pro'], description: '⚠️ Risk: банят за использование с не-CLI инструментами' },

  // ─── Free Tier Providers (API Key with free limits) ─────────
  { id: 'opencode-free', name: 'OpenCode Free', key: 'opencode-free', iconFile: 'opencode', type: 'openai-compatible', category: 'free-tier', authMethod: 'no-auth', baseUrl: 'https://opencode.ai/zen/v1', defaultModels: ['opencode-free'] },
  { id: 'openrouter', name: 'OpenRouter', key: 'openrouter', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://openrouter.ai/api/v1', defaultModels: [], apiKeyHint: 'sk-or-...' },
  { id: 'nvidia-nim', name: 'NVIDIA NIM', key: 'nvidia-nim', iconFile: 'nvidia', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://integrate.api.nvidia.com/v1', defaultModels: ['meta/llama-3.1-405b', 'mistralai/mixtral-8x22b'], apiKeyHint: 'nvapi-...' },
  { id: 'ollama-cloud', name: 'Ollama Cloud', key: 'ollama-cloud', iconFile: 'ollama', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://ollama.com/api', apiKeyHint: 'Создай на ollama.com → Settings → API Keys', description: 'Ollama Cloud — запуск больших моделей в облаке. Требуется аккаунт и API ключ' },
  { id: 'vertex-ai', name: 'Vertex AI', key: 'vertex-ai', iconFile: 'vertex', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://aiplatform.googleapis.com/v1', defaultModels: ['gemini-2.5-pro', 'claude-sonnet-4-5'], apiKeyHint: 'Bearer token...' },
  { id: 'cloudflare', name: 'Cloudflare AI', key: 'cloudflare', iconFile: 'cloudflare-ai', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://api.cloudflare.com/client/v4/accounts', defaultModels: ['@cf/meta/llama-3.1-8b', '@cf/mistral/mistral-7b'], apiKeyHint: 'Cloudflare API token' },
  { id: 'byteplus', name: 'BytePlus ModelArk', key: 'byteplus', type: 'openai-compatible', category: 'free-tier', authMethod: 'apikey', baseUrl: 'https://api.byteplus.com/api/v3', defaultModels: ['doubao-pro', 'doubao-lite'], apiKeyHint: 'sk-...' },

  // ─── API Key Providers ────────────────────────────────────
  { id: 'anthropic', name: 'Anthropic', key: 'anthropic', iconFile: 'anthropic', type: 'anthropic', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.anthropic.com', defaultModels: ['claude-sonnet-4-5', 'claude-opus-4-5', 'claude-haiku-4-5'], availableModels: ['claude-sonnet-4-5', 'claude-opus-4-5', 'claude-haiku-4-5', 'claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-3-20240307', 'claude-3.5-sonnet-20241022', 'claude-3.5-haiku-20241022'], apiKeyHint: 'sk-ant-...' },
  { id: 'openai', name: 'OpenAI', key: 'openai', type: 'openai', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.openai.com/v1', defaultModels: ['gpt-5.5', 'gpt-5.4-mini', 'gpt-5.4-nano'], availableModels: ['gpt-5.5', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5', 'gpt-5-mini', 'gpt-4o', 'gpt-4o-mini', 'o3-mini', 'o4-mini'], apiKeyHint: 'sk-...' },
  { id: 'alibaba', name: 'Alibaba (Qwen)', key: 'alibaba', iconFile: 'qwen', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModels: ['qwen-max', 'qwen-plus', 'qwen-turbo'], availableModels: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long', 'qwen-vl-max', 'qwen-coder-plus'], apiKeyHint: 'sk-...' },
  { id: 'alibaba-intl', name: 'Alibaba Intl', key: 'alibaba-intl', iconFile: 'qwen', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', defaultModels: ['qwen-max', 'qwen-plus'], availableModels: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long'], apiKeyHint: 'sk-...' },
  { id: 'cerebras', name: 'Cerebras', key: 'cerebras', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.cerebras.ai/v1', defaultModels: ['llama-3.3-70b', 'llama-3.1-8b'], availableModels: ['llama-3.3-70b', 'llama-3.1-8b', 'llama-3.1-70b'], apiKeyHint: 'csk-...' },
  { id: 'azure-openai', name: 'Azure OpenAI', key: 'azure-openai', iconFile: 'azure', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://{resource}.openai.azure.com/openai/deployments/{deployment}', defaultModels: ['gpt-4o', 'gpt-4o-mini'], description: 'Замените {resource} и {deployment} в URL', apiKeyHint: 'Azure API Key' },
  { id: 'cohere', name: 'Cohere', key: 'cohere', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.cohere.ai/v1', defaultModels: ['command-a', 'command-r-plus', 'command-r'], availableModels: ['command-a', 'command-r-plus', 'command-r', 'command-r-plus-08-2024', 'command-r-08-2024'], apiKeyHint: 'API key' },
  { id: 'command-code', name: 'Command Code', key: 'command-code', iconFile: 'cohere', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.cohere.ai/v1', defaultModels: ['command-r-plus-code'], availableModels: ['command-r-plus-code', 'command-r-code'], apiKeyHint: 'API key' },
  { id: 'deepseek', name: 'DeepSeek', key: 'deepseek', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.deepseek.com/v1', defaultModels: ['deepseek-chat', 'deepseek-reasoner'], availableModels: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'], apiKeyHint: 'sk-...' },
  { id: 'fireworks', name: 'Fireworks AI', key: 'fireworks', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.fireworks.ai/inference/v1', defaultModels: ['accounts/fireworks/models/llama-v3p3-70b-instruct', 'accounts/fireworks/models/deepseek-v3'], availableModels: ['accounts/fireworks/models/llama-v3p3-70b-instruct', 'accounts/fireworks/models/deepseek-v3', 'accounts/fireworks/models/llama-v3p1-405b', 'accounts/fireworks/models/qwen2p5-72b-instruct'], apiKeyHint: 'fw-...' },
  { id: 'glm-china', name: 'GLM (China)', key: 'glm-china', iconFile: 'glm', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModels: ['glm-4-plus', 'glm-4-flash', 'glm-4-air'], availableModels: ['glm-4-plus', 'glm-4-flash', 'glm-4-air', 'glm-4', 'glm-4v', 'codegeex-4'], apiKeyHint: 'API key' },
  { id: 'glm-coding', name: 'GLM Coding', key: 'glm-coding', iconFile: 'glm', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModels: ['codegeex-4', 'glm-4-flash'], availableModels: ['codegeex-4', 'glm-4-flash', 'glm-4-flash-code'], apiKeyHint: 'API key' },
  { id: 'groq', name: 'Groq', key: 'groq', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.groq.com/openai/v1', defaultModels: ['llama-3.3-70b', 'llama-3.1-8b-instant', 'qwen/qwen3-32b'], availableModels: ['llama-3.3-70b', 'llama-3.1-8b-instant', 'llama-3.1-70b', 'qwen/qwen3-32b', 'gemma2-9b-it', 'mixtral-8x7b'], apiKeyHint: 'gsk_...' },
  { id: 'hyperbolic', name: 'Hyperbolic', key: 'hyperbolic', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.hyperbolic.xyz/v1', defaultModels: ['meta-llama/Meta-Llama-3.1-405B', 'mistralai/Mixtral-8x22B'], availableModels: ['meta-llama/Meta-Llama-3.1-405B', 'mistralai/Mixtral-8x22B', 'meta-llama/Llama-3.3-70B'], apiKeyHint: 'API key' },
  { id: 'kimi', name: 'Kimi', key: 'kimi', iconFile: 'kimi', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.moonshot.cn/v1', defaultModels: ['moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-auto'], availableModels: ['moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k', 'moonshot-v1-auto', 'kimi-k2'], apiKeyHint: 'sk-...' },
  { id: 'minimax', name: 'Minimax (China)', key: 'minimax', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.minimax.chat/v1', defaultModels: ['abab6.5s-chat', 'abab6.5-chat'], availableModels: ['abab6.5s-chat', 'abab6.5-chat', 'abab6.5g-chat', 'abab5.5s-chat', 'minimax-text-01'], apiKeyHint: 'API key' },
  { id: 'minimax-coding', name: 'Minimax Coding', key: 'minimax-coding', iconFile: 'minimax', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.minimax.chat/v1', defaultModels: ['abab6.5-code'], availableModels: ['abab6.5-code'], apiKeyHint: 'API key' },
  { id: 'mistral', name: 'Mistral', key: 'mistral', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.mistral.ai/v1', defaultModels: ['mistral-medium-3.5', 'mistral-small-4', 'codestral'], availableModels: ['mistral-medium-3.5', 'mistral-medium-3', 'mistral-small-4', 'mistral-small-3.2', 'mistral-large-3', 'codestral', 'ministral-3-14b', 'ministral-3-8b', 'ministral-3-3b', 'pixtral-12b'], apiKeyHint: 'API key' },
  { id: 'nebius', name: 'Nebius AI', key: 'nebius', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.studio.nebius.ai/v1', defaultModels: ['llama-3.1-405b', 'mistral-large'], availableModels: ['llama-3.1-405b', 'mistral-large', 'llama-3.1-70b'], apiKeyHint: 'API key' },
  { id: 'ollama-local', name: 'Ollama Local', key: 'ollama-local', iconFile: 'ollama-local', type: 'openai-compatible', category: 'api-key', authMethod: 'no-auth', baseUrl: 'http://localhost:11434/v1', defaultModels: ['llama3.1', 'mistral', 'codellama', 'deepseek-coder'] },
  { id: 'perplexity', name: 'Perplexity', key: 'perplexity', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.perplexity.ai', defaultModels: ['sonar-pro', 'sonar', 'sonar-reasoning'], availableModels: ['sonar-pro', 'sonar', 'sonar-plus', 'sonar-reasoning', 'sonar-reasoning-pro'], apiKeyHint: 'pplx-...' },
  { id: 'siliconflow', name: 'SiliconFlow', key: 'siliconflow', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.siliconflow.cn/v1', defaultModels: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3'], availableModels: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3', 'meta-llama/Llama-3.1-405B-Instruct'], apiKeyHint: 'API key' },
  { id: 'together', name: 'Together AI', key: 'together', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.together.xyz/v1', defaultModels: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo'], availableModels: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo', 'Qwen/Qwen2.5-72B-Instruct-Turbo', 'deepseek-ai/DeepSeek-V3'], apiKeyHint: 'API key' },
  { id: 'vercel', name: 'Vercel AI Gateway', key: 'vercel', iconFile: 'vercel', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://gateway.vercel.com', defaultModels: [], apiKeyHint: 'API key' },
  { id: 'vertex-partner', name: 'Vertex Partner', key: 'vertex-partner', iconFile: 'vertex-partner', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://aiplatform.googleapis.com/v1', defaultModels: ['claude-sonnet-4-5', 'claude-opus-4-5'], availableModels: ['claude-sonnet-4-5', 'claude-opus-4-5', 'gemini-2.5-pro'], apiKeyHint: 'Bearer token...' },
  { id: 'volcengine', name: 'Volcengine Ark', key: 'volcengine', iconFile: 'byteplus', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultModels: ['doubao-pro-40k', 'doubao-pro-128k'], availableModels: ['doubao-pro-40k', 'doubao-pro-128k', 'doubao-lite-40k', 'doubao-lite-128k'], apiKeyHint: 'API key' },
  { id: 'xiaomi-mimo', name: 'Xiaomi MiMo', key: 'xiaomi-mimo', iconFile: 'xiaomi-mimo', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.mimo.ai/v1', defaultModels: ['mimo-v2'], availableModels: ['mimo-v2', 'mimo-v2-lite'], apiKeyHint: 'API key' },
  { id: 'blackbox', name: 'Blackbox AI', key: 'blackbox', iconFile: 'blackbox', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://api.blackbox.ai/api/v1', defaultModels: ['blackbox-pro'], availableModels: ['blackbox-pro', 'blackbox-api'], apiKeyHint: 'API key' },
  { id: 'chutes', name: 'Chutes AI', key: 'chutes', type: 'openai-compatible', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://llm.chutes.ai/v1', defaultModels: ['Llama-3.1-405B', 'Mixtral-8x22B'], availableModels: ['Llama-3.1-405B', 'Mixtral-8x22B', 'Llama-3.1-70B'], apiKeyHint: 'API key' },

  // ─── Anthropic-compatible ─────────────────────────────────
  { id: 'vertex-anthropic', name: 'Vertex Anthropic', key: 'vertex-anthropic', iconFile: 'vertex', type: 'anthropic', category: 'api-key', authMethod: 'apikey', baseUrl: 'https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/anthropic', defaultModels: ['claude-sonnet-4@20250514', 'claude-opus-4@20250514'], apiKeyHint: 'Bearer token...', description: 'Замените {project} и {location} в URL' },
]

// Grouped by category for display
export const PROVIDERS_BY_CATEGORY = {
  oauth: PROVIDER_CATALOG.filter(p => p.category === 'oauth'),
  freeTier: PROVIDER_CATALOG.filter(p => p.category === 'free-tier'),
  apiKey: PROVIDER_CATALOG.filter(p => p.category === 'api-key'),
}
