/** 与后端 app/core/ai_presets.py 保持一致。不含真实 Key。 */
export const AI_PRESETS = {
  deepseek: {
    label: 'DeepSeek',
    model: 'deepseek-v4-flash',
    baseUrl: 'https://api.deepseek.com',
  },
  openai: {
    label: 'OpenAI 新地址',
    model: 'gpt-4o-mini',
    baseUrl: 'https://api.openai.com/v1',
  },
  openai_legacy: {
    label: 'OpenAI 旧兼容',
    model: 'gpt-3.5-turbo',
    baseUrl: 'https://api.openai.com/v1',
  },
}

export const AI_PROVIDER_OPTIONS = [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'OpenAI 新地址', value: 'openai' },
  { label: 'OpenAI 旧兼容', value: 'openai_legacy' },
  { label: '其他（OpenAI 兼容）', value: 'other' },
]

export function applyAiPreset(provider) {
  const preset = AI_PRESETS[provider]
  if (!preset) return null
  return {
    provider,
    model: preset.model,
    base_url: preset.baseUrl,
  }
}
