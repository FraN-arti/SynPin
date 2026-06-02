// Provider catalog — all supported LLM providers

export interface ProviderInfo {
  id: string
  name: string
  type: 'openai' | 'openai-compatible' | 'anthropic'
  icon: string
  category: 'oauth' | 'free-tier' | 'api-key'
  baseUrl: string
  defaultModels: string[]
  description?: string
}

export const PROVIDER_CATALOG: ProviderInfo[] = [
  // ─── OAuth Providers ──────────────────────────────────────
  { id: 'claude-code', name: 'Claude Code', type: 'anthropic', icon: '🟣', category: 'oauth', baseUrl: 'https://api.anthropic.com', defaultModels: ['claude-sonnet-4', 'claude-opus-4'] },
  { id: 'cursor', name: 'Cursor IDE', type: 'openai-compatible', icon: '⚡', category: 'oauth', baseUrl: 'https://api.cursor.sh', defaultModels: ['claude-3.5-sonnet', 'gpt-4o'] },
  { id: 'github-copilot', name: 'GitHub Copilot', type: 'openai-compatible', icon: '🐙', category: 'oauth', baseUrl: 'https://api.githubcopilot.com', defaultModels: ['gpt-4o', 'claude-3.5-sonnet'] },
  { id: 'cline', name: 'Cline', type: 'openai-compatible', icon: '🤖', category: 'oauth', baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o', 'claude-sonnet-4'] },
  { id: 'kilo-code', name: 'Kilo Code', type: 'openai-compatible', icon: '🔷', category: 'oauth', baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o'] },
  { id: 'openai-codex', name: 'OpenAI Codex', type: 'openai', icon: '🔵', category: 'oauth', baseUrl: 'https://api.openai.com', defaultModels: ['o1', 'o1-mini', 'gpt-4o'] },
  { id: 'xAI-grok', name: 'xAI (Grok)', type: 'openai-compatible', icon: '✖️', category: 'oauth', baseUrl: 'https://api.x.ai/v1', defaultModels: ['grok-2', 'grok-2-vision'] },
  { id: 'antigravity', name: 'Antigravity', type: 'openai-compatible', icon: '🪶', category: 'oauth', baseUrl: 'https://api.openai.com', defaultModels: ['gpt-4o'] },

  // ─── Free Tier Providers ──────────────────────────────────
  { id: 'kiro-ai', name: 'Kiro AI', type: 'openai-compatible', icon: '🌀', category: 'free-tier', baseUrl: 'https://api.kiro.dev', defaultModels: ['kiro-v1'] },
  { id: 'gemini-cli', name: 'Gemini CLI', type: 'openai-compatible', icon: '💎', category: 'free-tier', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', defaultModels: ['gemini-2.0-flash', 'gemini-2.5-pro'] },
  { id: 'qoder', name: 'Qoder', type: 'openai-compatible', icon: '🔶', category: 'free-tier', baseUrl: 'https://api.qoder.com', defaultModels: ['qoder-v1'] },
  { id: 'opencode-free', name: 'OpenCode Free', type: 'openai-compatible', icon: '🆓', category: 'free-tier', baseUrl: 'https://api.opencode.ai', defaultModels: ['opencode-free'] },
  { id: 'openrouter', name: 'OpenRouter', type: 'openai-compatible', icon: '🌐', category: 'free-tier', baseUrl: 'https://openrouter.ai/api/v1', defaultModels: ['openai/gpt-4o', 'anthropic/claude-sonnet-4', 'google/gemini-2.5-pro'] },
  { id: 'nvidia-nim', name: 'NVIDIA NIM', type: 'openai-compatible', icon: '🟢', category: 'free-tier', baseUrl: 'https://integrate.api.nvidia.com/v1', defaultModels: ['meta/llama-3.1-405b', 'mistralai/mixtral-8x22b'] },
  { id: 'ollama-cloud', name: 'Ollama Cloud', type: 'openai-compatible', icon: '🦙', category: 'free-tier', baseUrl: 'https://ollama.ai/api', defaultModels: ['llama3.1', 'mistral', 'codellama'] },
  { id: 'vertex-ai', name: 'Vertex AI', type: 'openai-compatible', icon: '🔺', category: 'free-tier', baseUrl: 'https://aiplatform.googleapis.com/v1', defaultModels: ['gemini-2.5-pro', 'claude-sonnet-4'] },
  { id: 'cloudflare', name: 'Cloudflare', type: 'openai-compatible', icon: '🟠', category: 'free-tier', baseUrl: 'https://api.cloudflare.com/client/v4/accounts', defaultModels: ['@cf/meta/llama-3.1-8b', '@cf/mistral/mistral-7b'] },
  { id: 'byteplus', name: 'BytePlus ModelArk', type: 'openai-compatible', icon: '🔷', category: 'free-tier', baseUrl: 'https://api.byteplus.com', defaultModels: ['doubao-pro', 'doubao-lite'] },

  // ─── API Key Providers ────────────────────────────────────
  { id: 'anthropic', name: 'Anthropic', type: 'anthropic', icon: '🟣', category: 'api-key', baseUrl: 'https://api.anthropic.com', defaultModels: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-3-20240307'] },
  { id: 'openai', name: 'OpenAI', type: 'openai', icon: '🔵', category: 'api-key', baseUrl: 'https://api.openai.com/v1', defaultModels: ['gpt-4o', 'gpt-4o-mini', 'o1', 'o1-mini', 'o3-mini'] },
  { id: 'alibaba', name: 'Alibaba', type: 'openai-compatible', icon: '🟠', category: 'api-key', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModels: ['qwen-max', 'qwen-plus', 'qwen-turbo'] },
  { id: 'alibaba-intl', name: 'Alibaba Intl', type: 'openai-compatible', icon: '🌏', category: 'api-key', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', defaultModels: ['qwen-max', 'qwen-plus'] },
  { id: 'cerebras', name: 'Cerebras', type: 'openai-compatible', icon: '🧠', category: 'api-key', baseUrl: 'https://api.cerebras.ai/v1', defaultModels: ['llama3.1-8b', 'llama3.1-70b'] },
  { id: 'azure-openai', name: 'Azure OpenAI', type: 'openai-compatible', icon: '☁️', category: 'api-key', baseUrl: 'https://{resource}.openai.azure.com/openai/deployments/{deployment}', defaultModels: ['gpt-4o', 'gpt-4o-mini'] },
  { id: 'cohere', name: 'Cohere', type: 'openai-compatible', icon: '🔵', category: 'api-key', baseUrl: 'https://api.cohere.ai/v1', defaultModels: ['command-r-plus', 'command-r'] },
  { id: 'command-code', name: 'Command Code', type: 'openai-compatible', icon: '⌨️', category: 'api-key', baseUrl: 'https://api.cohere.ai/v1', defaultModels: ['command-r-plus-code'] },
  { id: 'deepseek', name: 'DeepSeek', type: 'openai-compatible', icon: '🐋', category: 'api-key', baseUrl: 'https://api.deepseek.com/v1', defaultModels: ['deepseek-chat', 'deepseek-coder'] },
  { id: 'fireworks', name: 'Fireworks AI', type: 'openai-compatible', icon: '🎆', category: 'api-key', baseUrl: 'https://api.fireworks.ai/inference/v1', defaultModels: ['accounts/fireworks/models/llama-v3p1-405b', 'accounts/fireworks/models/mixtral-8x22b'] },
  { id: 'glm-china', name: 'GLM (China)', type: 'openai-compatible', icon: '🇨🇳', category: 'api-key', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModels: ['glm-4', 'glm-4v', 'glm-4-flash'] },
  { id: 'glm-coding', name: 'GLM Coding', type: 'openai-compatible', icon: '💻', category: 'api-key', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModels: ['codegeex-4', 'glm-4-code'] },
  { id: 'groq', name: 'Groq', type: 'openai-compatible', icon: '⚡', category: 'api-key', baseUrl: 'https://api.groq.com/openai/v1', defaultModels: ['llama-3.1-70b', 'llama-3.1-8b', 'mixtral-8x7b'] },
  { id: 'hyperbolic', name: 'Hyperbolic', type: 'openai-compatible', icon: '🔮', category: 'api-key', baseUrl: 'https://api.hyperbolic.xyz/v1', defaultModels: ['meta-llama/Meta-Llama-3.1-405B', 'mistralai/Mixtral-8x22B'] },
  { id: 'kimi', name: 'Kimi', type: 'openai-compatible', icon: '🌙', category: 'api-key', baseUrl: 'https://api.moonshot.cn/v1', defaultModels: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'] },
  { id: 'minimax', name: 'Minimax (China)', type: 'openai-compatible', icon: '🎭', category: 'api-key', baseUrl: 'https://api.minimax.chat/v1', defaultModels: ['abab6.5-chat', 'abab6.5s-chat'] },
  { id: 'minimax-coding', name: 'Minimax Coding', type: 'openai-compatible', icon: '🎭', category: 'api-key', baseUrl: 'https://api.minimax.chat/v1', defaultModels: ['abab6.5-code'] },
  { id: 'mistral', name: 'Mistral', type: 'openai-compatible', icon: '🌊', category: 'api-key', baseUrl: 'https://api.mistral.ai/v1', defaultModels: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest'] },
  { id: 'nebius', name: 'Nebius AI', type: 'openai-compatible', icon: '☁️', category: 'api-key', baseUrl: 'https://api.studio.nebius.ai/v1', defaultModels: ['llama-3.1-405b', 'mistral-large'] },
  { id: 'ollama-local', name: 'Ollama Local', type: 'openai-compatible', icon: '🦙', category: 'api-key', baseUrl: 'http://localhost:11434/v1', defaultModels: ['llama3.1', 'mistral', 'codellama', 'deepseek-coder'] },
  { id: 'perplexity', name: 'Perplexity', type: 'openai-compatible', icon: '🔍', category: 'api-key', baseUrl: 'https://api.perplexity.ai', defaultModels: ['sonar-pro', 'sonar', 'llama-3.1-sonar-large'] },
  { id: 'siliconflow', name: 'SiliconFlow', type: 'openai-compatible', icon: '🔬', category: 'api-key', baseUrl: 'https://api.siliconflow.cn/v1', defaultModels: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3'] },
  { id: 'together', name: 'Together AI', type: 'openai-compatible', icon: '🤝', category: 'api-key', baseUrl: 'https://api.together.xyz/v1', defaultModels: ['meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo', 'mistralai/Mixtral-8x22B-Instruct-v0.1'] },
  { id: 'vercel', name: 'Vercel AI Gateway', type: 'openai-compatible', icon: '▲', category: 'api-key', baseUrl: 'https://gateway.vercel.com', defaultModels: ['openai/gpt-4o', 'anthropic/claude-sonnet-4'] },
  { id: 'vertex-partner', name: 'Vertex Partner', type: 'openai-compatible', icon: '🔺', category: 'api-key', baseUrl: 'https://aiplatform.googleapis.com/v1', defaultModels: ['claude-sonnet-4', 'claude-opus-4'] },
  { id: 'volcengine', name: 'Volcengine Ark', type: 'openai-compatible', icon: '🌋', category: 'api-key', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultModels: ['doubao-pro-40k', 'doubao-pro-128k'] },
  { id: 'xiaomi-mimo', name: 'Xiaomi MiMo', type: 'openai-compatible', icon: '📱', category: 'api-key', baseUrl: 'https://api.mimo.com/v1', defaultModels: ['mimo-v2'] },
  { id: 'blackbox', name: 'Blackbox AI', type: 'openai-compatible', icon: '📦', category: 'api-key', baseUrl: 'https://api.blackbox.ai', defaultModels: ['blackbox-pro'] },
  { id: 'chutes', name: 'Chutes AI', type: 'openai-compatible', icon: '🎢', category: 'api-key', baseUrl: 'https://llm.chutes.ai/v1', defaultModels: ['Llama-3.1-405B', 'Mixtral-8x22B'] },

  // ─── Anthropic-compatible ─────────────────────────────────
  { id: 'vertex-anthropic', name: 'Vertex Anthropic', type: 'anthropic', icon: '🟣', category: 'api-key', baseUrl: 'https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/anthropic', defaultModels: ['claude-sonnet-4@20250514', 'claude-opus-4@20250514'] },
]

// Grouped by category for display
export const PROVIDERS_BY_CATEGORY = {
  oauth: PROVIDER_CATALOG.filter(p => p.category === 'oauth'),
  freeTier: PROVIDER_CATALOG.filter(p => p.category === 'free-tier'),
  apiKey: PROVIDER_CATALOG.filter(p => p.category === 'api-key'),
}
