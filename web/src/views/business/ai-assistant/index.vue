<script setup>
import { onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { AI_PROVIDER_OPTIONS, applyAiPreset } from '@/constants/aiPresets'

defineOptions({ name: 'AI 助手' })

const messages = ref([
  {
    role: 'assistant',
    content:
      '你好！我是企业资产管理系统的 AI 助手。你可以问我资产、员工、审批相关的问题，也可以让我帮你分析数据。支持上传图片（截图/照片）让我"看"——图片理解走独立视觉模型（DeepSeek 不支持直接看图）。',
  },
])
const input = ref('')
const loading = ref(false)
const visionLoading = ref(false)

const configVisible = ref(false)
const configForm = ref({
  provider: 'deepseek',
  api_key: '',
  model: 'deepseek-v4-flash',
  base_url: 'https://api.deepseek.com',
  vision_provider: '',
  vision_api_key: '',
  vision_model: '',
  vision_base_url: '',
})
const configSaved = ref(false)
const keyMasked = ref('')
const visionKeyMasked = ref('')
const visionSaved = ref(false)

const providerOptions = AI_PROVIDER_OPTIONS

const visionProviderOptions = [
  { label: '通义千问（DashScope）', value: 'qwen' },
  { label: '智谱 GLM', value: 'zhipu' },
  { label: 'OpenAI', value: 'openai' },
  { label: '其他（OpenAI 兼容）', value: 'other' },
]

// 图片理解：把图片 base64 交给视觉模型描述，结果作为 assistant 消息展示
async function handleImageSelected(file) {
  if (!file) return
  if (visionLoading.value || loading.value) return
  const maxSize = 5 * 1024 * 1024
  if (file.size > maxSize) {
    window.$message?.error('图片不能超过 5MB')
    return
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    window.$message?.error('仅支持 jpg/png/webp 格式')
    return
  }
  visionLoading.value = true
  try {
    const base64 = await fileToBase64(file)
    const res = await api.aiVision({
      image_base64: base64,
      prompt: '请详细描述这张图片的内容，包括所有可见的文字、数字与关键信息',
    })
    if (res.code === 200) {
      messages.value.push({ role: 'user', content: `[图片] ${file.name || '截图'}` })
      messages.value.push({ role: 'assistant', content: `📷 图片理解结果：\n${res.data.content}` })
    } else {
      messages.value.push({ role: 'assistant', content: `⚠️ ${res.msg || '图片理解失败'}` })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '⚠️ 图片上传失败，请检查视觉模型配置' })
  }
  visionLoading.value = false
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      const idx = result.indexOf(',')
      resolve(idx >= 0 ? result.slice(idx + 1) : result)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  try {
    const history = messages.value.slice(-10).map((m) => ({ role: m.role, content: m.content }))
    const res = await api.aiChat({ messages: history, temperature: 0.5 })
    if (res.code === 200) {
      const data = res.data
      messages.value.push({
        role: 'assistant',
        content: data.content,
        fromCache: data.from_cache,
      })
    } else {
      messages.value.push({ role: 'assistant', content: `⚠️ ${res.msg || '调用失败'}` })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '⚠️ 网络错误，请稍后再试' })
  }
  loading.value = false
  scrollToBottom()
}

function scrollToBottom() {
  setTimeout(() => {
    const box = document.querySelector('.chat-box')
    if (box) box.scrollTop = box.scrollHeight
  }, 50)
}

async function openConfig() {
  const res = await api.getMyApiConfig()
  if (res.code === 200) {
    keyMasked.value = res.data.api_key_masked
    configSaved.value = res.data.has_key
    visionKeyMasked.value = res.data.vision_api_key_masked
    visionSaved.value = res.data.has_vision_key
    const provider = res.data.provider || 'deepseek'
    const preset = applyAiPreset(provider)
    configForm.value = {
      provider,
      api_key: '',
      model: res.data.model || preset?.model || 'deepseek-v4-flash',
      base_url: res.data.base_url || preset?.base_url || 'https://api.deepseek.com',
      vision_provider: res.data.vision_provider || '',
      vision_api_key: '',
      vision_model: res.data.vision_model || '',
      vision_base_url: res.data.vision_base_url || '',
    }
  }
  configVisible.value = true
}

function onProviderChange(provider) {
  const preset = applyAiPreset(provider)
  if (!preset) return
  configForm.value.model = preset.model
  configForm.value.base_url = preset.base_url
}

async function saveConfig() {
  if (!configForm.value.api_key && !configSaved.value) {
    window.$message?.warning('请填写 API Key')
    return
  }
  await api.saveApiConfig(configForm.value)
  window.$message?.success('API 配置已保存（密钥已加密存储）')
  configVisible.value = false
}

onMounted(() => {
  api.getMyApiConfig().then((res) => {
    if (res.code === 200) {
      keyMasked.value = res.data.api_key_masked
      configSaved.value = res.data.has_key
      visionKeyMasked.value = res.data.vision_api_key_masked
      visionSaved.value = res.data.has_vision_key
    }
  })
})
</script>

<template>
  <CommonPage :show-header="false">
    <div class="ai-layout">
      <!-- 对话区：浅色/暗色均显式设置背景与文字色，避免暗色主题下「白底+浅字」不可读 -->
      <div class="ai-chat-panel">
        <div class="chat-box">
          <div v-for="(m, i) in messages" :key="i" class="chat-row">
            <div v-if="m.role === 'user'" class="chat-row-user">
              <div class="bubble bubble-user">
                {{ m.content }}
              </div>
            </div>
            <div v-else class="chat-row-assistant">
              <div class="ai-avatar">AI</div>
              <div class="bubble bubble-assistant">
                {{ m.content }}
                <div v-if="m.fromCache" class="cache-tip">⚡ 缓存结果（未消耗 API）</div>
              </div>
            </div>
          </div>
          <div v-if="loading || visionLoading" class="loading-tip">
            {{ visionLoading ? '🖼️ 图片理解中...' : 'AI 思考中...' }}
          </div>
        </div>
        <div class="composer">
          <label class="upload-btn" title="上传图片（截图/照片）让 AI 看图">
            📎
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="hidden-file"
              @change="
                (e) => {
                  handleImageSelected(e.target.files?.[0])
                  e.target.value = ''
                }
              "
            />
          </label>
          <NInput
            v-model:value="input"
            type="textarea"
            :rows="2"
            placeholder="输入问题，Enter 发送（Shift+Enter 换行）；📎 上传图片让 AI 看图"
            @keydown.enter.prevent="!$event.shiftKey && send()"
          />
          <NButton type="primary" :loading="loading" class="composer-action" @click="send">
            发送
          </NButton>
          <NButton class="composer-action" @click="openConfig">
            {{ configSaved ? `🔑 已配置（${keyMasked}）` : '🔑 配置 API' }}
          </NButton>
        </div>
      </div>
    </div>

    <NModal v-model:show="configVisible" preset="card" title="AI 模型 API 配置" style="width: 560px">
      <p class="config-hint">
        选好服务商后一般只粘贴 Key。密钥加密存放，不会进仓库，也不会送给模型。
        助手是只读笼子：不能跑 SQL / Shell / 读盘，也不能问服务器密码。
        <template v-if="configSaved">当前已配置：{{ keyMasked }}（留空保存则保持不变）</template>
      </p>
      <NForm label-placement="left" label-width="100" :model="configForm">
        <NFormItem label="服务商">
          <NSelect
            v-model:value="configForm.provider"
            :options="providerOptions"
            @update:value="onProviderChange"
          />
        </NFormItem>
        <NFormItem label="API Key">
          <NInput
            v-model:value="configForm.api_key"
            type="password"
            show-password-on="click"
            placeholder="只粘贴 Key，不要提交到 Git"
          />
        </NFormItem>
        <NFormItem label="模型名">
          <NInput v-model:value="configForm.model" placeholder="deepseek-v4-flash" />
        </NFormItem>
        <NFormItem label="Base URL">
          <NInput v-model:value="configForm.base_url" placeholder="https://api.deepseek.com" />
        </NFormItem>
        <NFormItem label="视觉服务商">
          <NSelect
            v-model:value="configForm.vision_provider"
            :options="visionProviderOptions"
            clearable
            placeholder="（可选）图片理解用"
          />
        </NFormItem>
        <NFormItem label="视觉 API Key">
          <NInput
            v-model:value="configForm.vision_api_key"
            type="password"
            show-password-on="click"
            placeholder="（可选）视觉模型 Key"
          />
        </NFormItem>
        <NFormItem label="视觉模型名">
          <NInput
            v-model:value="configForm.vision_model"
            placeholder="qwen-vl-plus / glm-4v / gpt-4o-mini"
          />
        </NFormItem>
        <NFormItem label="视觉 Base URL">
          <NInput
            v-model:value="configForm.vision_base_url"
            placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
          />
        </NFormItem>
      </NForm>
      <p class="config-foot">
        💡 DeepSeek 不支持直接看图：配置视觉模型后，上传图片会先由视觉模型转成文字描述（"眼睛"），
        可再交给 DeepSeek 分析（"大脑"）。视觉模型配置可选，未配置时上传图片会提示。
        <template v-if="visionSaved">当前视觉模型已配置：{{ visionKeyMasked }}</template>
      </p>
      <template #footer>
        <NButton type="primary" style="width: 100%" @click="saveConfig">保存配置（加密存储）</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.ai-layout {
  display: flex;
  height: calc(100vh - 120px);
  gap: 16px;
}

.ai-chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  padding: 16px;
  /* 浅色：白底深字 */
  background: #ffffff;
  color: #1f2225;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.chat-box {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 12px;
}

.chat-row {
  margin-bottom: 14px;
}

.chat-row-user {
  display: flex;
  justify-content: flex-end;
}

.chat-row-assistant {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
}

.bubble {
  max-width: 75%;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-user {
  background: #2080f0;
  color: #ffffff;
  border-radius: 10px 10px 2px 10px;
}

.bubble-assistant {
  background: #f0f2f5;
  color: #1f2225;
  border-radius: 10px 10px 10px 2px;
}

.ai-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #18a058;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}

.cache-tip {
  font-size: 11px;
  color: #888;
  margin-top: 6px;
}

.loading-tip {
  color: #888;
  font-size: 13px;
  padding: 8px 0;
}

.composer {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.upload-btn {
  cursor: pointer;
  align-self: flex-end;
  font-size: 22px;
  line-height: 1;
  user-select: none;
}

.hidden-file {
  display: none;
}

.composer-action {
  align-self: flex-end;
}

.config-hint {
  color: #666;
  font-size: 13px;
  margin-bottom: 12px;
}

.config-foot {
  color: #999;
  font-size: 12px;
  margin-top: 8px;
}

/* 暗色：vueuse useDark 在 html 上挂 .dark；面板与气泡必须深底 + 浅字 */
:global(html.dark) .ai-chat-panel {
  background: #18181c;
  color: #e8e8ed;
  box-shadow: none;
  border-color: rgba(255, 255, 255, 0.09);
}

:global(html.dark) .bubble-assistant {
  background: #2a2a30;
  color: #e8e8ed;
}

:global(html.dark) .bubble-user {
  background: #2d6fd4;
  color: #ffffff;
}

:global(html.dark) .cache-tip,
:global(html.dark) .loading-tip {
  color: #a0a0ab;
}

:global(html.dark) .config-hint {
  color: #b0b0ba;
}

:global(html.dark) .config-foot {
  color: #8a8a96;
}
</style>
