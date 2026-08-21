<script setup>
import { h, onMounted, ref } from 'vue'
import { NAlert, NButton, NInput, NPopconfirm, NUpload } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { usePermissionStore, useUserStore } from '@/store'
import api from '@/api'

defineOptions({ name: '知识库' })

const EXAMPLES = [
  '调拨怎么审批？',
  '调拨通过后资产还在用吗？',
  '质保到期提醒谁？',
  '手机怎么扫资产码？',
  '盘点会删掉资产吗？',
  '闲置资产能不能送修？',
]

const $table = ref(null)
const question = ref('')
const asking = ref(false)
const answer = ref('')
const citations = ref([])
const retrieval = ref(null)
const docCount = ref(0)
const permissionStore = usePermissionStore()
const userStore = useUserStore()
const steward = ref(null)
const stewardLoading = ref(false)
const drafts = ref([])
const draftNotice = ref('')
const draftErrors = ref([])

function hasApi(p) {
  return (permissionStore.accessApis || []).includes(p)
}

function embedLabel(kind) {
  return kind === 'api' ? '合格向量' : '无向量（词面）'
}

function sourceLabel(source) {
  if (source === 'builtin') return '内置'
  if (source === 'upload') return '上传'
  if (source === 'steward') return '管家'
  return source || '-'
}

function modeLabel() {
  if (!retrieval.value) return ''
  return retrieval.value.mode === 'hybrid' ? '词面 + 语义' : '中文词面检索'
}

async function loadData() {
  const res = await api.getKbList()
  retrieval.value = res.data?.retrieval || null
  const list = res.data?.list || []
  docCount.value = list.length
  return { data: list, total: list.length }
}

async function onUpload({ file, onFinish, onError }) {
  const raw = file?.file
  if (!raw) {
    onError && onError()
    return
  }
  const fd = new FormData()
  fd.append('file', raw)
  try {
    await api.uploadKbDoc(fd)
    $message.success('已入库')
    $table.value?.handleSearch()
    onFinish && onFinish()
  } catch (e) {
    $message.error(e?.message || e?.msg || '入库失败')
    onError && onError()
  }
}

async function seedBuiltin() {
  try {
    const res = await api.seedKbBuiltin()
    const n = res.data?.chunk_count
    $message.success(n ? `已导入内置操作说明（${n} 段）` : '已导入内置操作说明')
    $table.value?.handleSearch()
  } catch (e) {
    $message.error(e?.message || e?.msg || '导入失败')
  }
}

async function ask() {
  if (!question.value.trim()) {
    $message.warning('请输入问题')
    return
  }
  asking.value = true
  try {
    const res = await api.askKb({ question: question.value.trim() })
    answer.value = res.data?.answer || ''
    citations.value = res.data?.citations || []
    if (res.data?.retrieval) retrieval.value = res.data.retrieval
  } catch (e) {
    answer.value = e?.message || e?.msg || '问答失败'
    citations.value = []
  } finally {
    asking.value = false
  }
}

function useExample(text) {
  question.value = text
  ask()
}

async function analyzeKb() {
  stewardLoading.value = true
  try {
    const res = await api.analyzeKb()
    steward.value = res.data || null
    drafts.value = []
    draftNotice.value = ''
    draftErrors.value = []
  } catch (e) {
    $message.error(e?.message || e?.msg || '分析失败')
  } finally {
    stewardLoading.value = false
  }
}

async function draftGaps() {
  stewardLoading.value = true
  try {
    const res = await api.draftKbGaps({})
    drafts.value = res.data?.drafts || []
    draftNotice.value = res.data?.notice || ''
    draftErrors.value = res.data?.errors || []
    if (!drafts.value.length) {
      $message.info(draftNotice.value || '没有可生成的缺章')
    }
  } catch (e) {
    $message.error(e?.message || e?.msg || '生成草稿失败')
  } finally {
    stewardLoading.value = false
  }
}

async function confirmDraft(row) {
  try {
    await api.ingestKbDraft({ title: row.title, text: row.text })
    $message.success('已入库')
    drafts.value = drafts.value.filter((item) => item.topic !== row.topic)
    $table.value?.handleSearch()
    await analyzeKb()
  } catch (e) {
    $message.error(e?.message || e?.msg || '入库失败')
  }
}

async function removeRow(row) {
  await api.deleteKbDoc({ id: row.id })
  $message.success('已删除')
  $table.value?.handleSearch()
}

const columns = [
  { title: '标题', key: 'title' },
  {
    title: '来源',
    key: 'source',
    width: 90,
    render: (row) => sourceLabel(row.source),
  },
  { title: '切片', key: 'chunk_count', width: 70 },
  {
    title: '向量',
    key: 'embed_kind',
    width: 120,
    render: (row) => embedLabel(row.embed_kind),
  },
  { title: '时间', key: 'created_at', width: 170 },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) => {
      if (!hasApi('delete/api/v1/kb/delete')) return null
      return h(
        NPopconfirm,
        { onPositiveClick: () => removeRow(row) },
        {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, () => '删除'),
          default: () => `删除「${row.title}」？`,
        }
      )
    },
  },
]

onMounted(() => $table.value?.handleSearch())
</script>

<template>
  <CommonPage>
    <template #action>
      <div class="kb-actions">
        <NUpload :show-file-list="false" accept=".txt,.md" :custom-request="onUpload">
          <NButton v-if="hasApi('post/api/v1/kb/upload')" type="primary">上传 txt/md</NButton>
        </NUpload>
        <NButton v-if="hasApi('post/api/v1/kb/seed-builtin')" @click="seedBuiltin">
          导入内置操作说明
        </NButton>
        <NButton v-if="userStore.isSuperUser" :loading="stewardLoading" @click="analyzeKb">
          分析框架
        </NButton>
      </div>
    </template>

    <NAlert
      v-if="retrieval?.notice"
      :type="retrieval.degraded ? 'warning' : 'info'"
      class="kb-alert"
    >
      <div class="kb-alert__mode">{{ modeLabel() }}</div>
      {{ retrieval.notice }}
    </NAlert>

    <div v-if="docCount === 0" class="kb-empty">
      还没有入库文档。请先点右上角「导入内置操作说明」，或上传自己写的 txt/md。
    </div>

    <section class="kb-ask">
      <div class="kb-examples">
        <button
          v-for="item in EXAMPLES"
          :key="item"
          type="button"
          class="kb-chip"
          @click="useExample(item)"
        >
          {{ item }}
        </button>
      </div>
      <NInput
        v-model:value="question"
        type="textarea"
        :rows="2"
        maxlength="500"
        placeholder="根据已入库文档提问，例如：调拨怎么走审批？"
      />
      <NButton type="primary" :loading="asking" class="kb-ask__btn" @click="ask">提问</NButton>
      <div v-if="answer" class="kb-answer">{{ answer }}</div>
      <div v-if="citations.length" class="kb-cites">
        <div class="kb-cites__title">引用</div>
        <ol>
          <li v-for="item in citations" :key="item.n">
            <strong>《{{ item.title }}》</strong>
            {{ item.snippet }}
          </li>
        </ol>
      </div>
    </section>

    <section v-if="userStore.isSuperUser && steward" class="kb-steward">
      <h3>知识库管家</h3>
      <p class="kb-steward__meta">
        文档 {{ steward.doc_count }} 份，切片 {{ steward.chunk_count }} 段。已覆盖
        {{ (steward.covered || []).length }} / {{ (steward.topics || []).length }} 章。草稿需你确认才入库。
      </p>
      <p v-if="(steward.missing || []).length">缺章：{{ steward.missing.join('、') }}</p>
      <p v-else>没有整章缺失。</p>
      <p v-if="(steward.weak || []).length">
        偏弱：{{ steward.weak.map((item) => item.topic).join('、') }}
      </p>
      <div v-if="(steward.duplicates || []).length" class="kb-steward__dups">
        <div>可能重复</div>
        <ul>
          <li v-for="(item, index) in steward.duplicates" :key="index">
            《{{ item.left }}》≈《{{ item.right }}》 {{ item.snippet }}
          </li>
        </ul>
      </div>
      <NButton :loading="stewardLoading" type="primary" @click="draftGaps">生成缺章草稿</NButton>
      <p v-if="draftNotice" class="kb-steward__note">{{ draftNotice }}</p>
      <p v-for="err in draftErrors" :key="err" class="kb-steward__err">{{ err }}</p>
      <article v-for="row in drafts" :key="row.topic" class="kb-draft">
        <pre>{{ row.text }}</pre>
        <NPopconfirm @positive-click="() => confirmDraft(row)">
          <template #trigger>
            <NButton size="small" type="primary">确认入库</NButton>
          </template>
          确认把「{{ row.title }}」写入知识库？不会自动覆盖内置说明。
        </NPopconfirm>
      </article>
    </section>

    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="loadData"
      :query-items="{}"
      :remote="false"
    />
  </CommonPage>
</template>

<style scoped>
.kb-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.kb-alert {
  margin-bottom: 16px;
}
.kb-alert__mode {
  margin-bottom: 4px;
  font-weight: 600;
}
.kb-empty {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px dashed var(--shell-border, #d9dee8);
  border-radius: 8px;
  color: var(--shell-text-muted, #666);
  background: var(--shell-surface-muted, #f5f7fa);
  font-size: 13px;
  line-height: 1.6;
}
.kb-ask {
  margin-bottom: 16px;
}
.kb-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.kb-chip {
  padding: 6px 10px;
  border: 1px solid var(--shell-border, #d9dee8);
  border-radius: 8px;
  color: var(--shell-text, #1f2329);
  background: var(--shell-surface, #fff);
  font-size: 12px;
  cursor: pointer;
}
.kb-chip:hover {
  border-color: var(--shell-accent, #3b82f6);
  color: var(--shell-accent, #3b82f6);
}
.kb-ask__btn {
  margin-top: 8px;
}
.kb-answer {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--shell-border, #d9dee8);
  border-radius: 8px;
  background: var(--shell-surface-muted, #f5f7fa);
  color: var(--shell-text, #1f2329);
  white-space: pre-wrap;
  line-height: 1.65;
}
.kb-cites {
  margin-top: 12px;
}
.kb-cites__title {
  margin-bottom: 6px;
  font-weight: 600;
}
.kb-steward {
  margin: 0 0 16px;
  padding: 14px;
  border: 1px solid var(--shell-border, #d9dee8);
  border-radius: 8px;
  background: var(--shell-surface, #fff);
}
.kb-steward h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.kb-steward__meta,
.kb-steward__note,
.kb-steward p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--shell-text, #1f2329);
}
.kb-steward__err {
  color: #b42318;
  font-size: 12px;
}
.kb-steward__dups ul {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 12px;
  color: var(--shell-text-muted, #666);
}
.kb-draft {
  margin-top: 12px;
  padding: 10px;
  border-radius: 8px;
  background: var(--shell-surface-muted, #f5f7fa);
}
.kb-draft pre {
  margin: 0 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
}
.kb-cites ol {
  margin: 0;
  padding-left: 20px;
  color: var(--shell-text-muted, #666);
  line-height: 1.6;
}
.kb-cites li {
  margin-bottom: 6px;
}
@media (max-width: 768px) {
  .kb-actions {
    justify-content: flex-start;
  }
}
</style>
