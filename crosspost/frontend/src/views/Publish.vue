<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, MagicStick } from '@element-plus/icons-vue'
import { fetchPlatforms, fetchAccounts, startPublish, subscribePublish, uploadFile, generateMaster } from '../api.js'

const platforms = ref([])
const accounts = ref([])

const form = reactive({
  file: '',
  fileName: '',
  title: '',
  description: '',
  tags: '',
  cover: '',
  coverName: '',
  use_ai: true,
  dry_run: false,
  targets: [],                        // [{platform, account}]
  extras: { bilibili: { tid: 21 } },  // {platform: {key: value}}
})

const uploadProgress = ref(0)  // 0..1 for the video upload itself
const uploading = ref(false)

// AI generate-master dialog
const aiOpen = ref(false)
const aiTopic = ref('')
const aiStyle = ref('')
const aiBusy = ref(false)

async function aiGenerate() {
  if (!aiTopic.value.trim()) {
    ElMessage.warning('描述一下视频内容')
    return
  }
  aiBusy.value = true
  try {
    const data = await generateMaster(aiTopic.value, aiStyle.value)
    form.title = data.title || form.title
    form.description = data.description || form.description
    form.tags = (data.tags && data.tags.length) ? data.tags.join(',') : form.tags
    aiOpen.value = false
    ElMessage.success('已填入，可继续微调')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'AI 生成失败，检查 API key')
  } finally {
    aiBusy.value = false
  }
}

// publish progress: per "platform:account" key → { stage: 'adapt'|'upload', status: 'pending'|'running'|'done'|'fail', error?, result?, adapted? }
const progress = ref({})
const publishing = ref(false)
let currentES = null

onMounted(async () => {
  platforms.value = await fetchPlatforms()
  accounts.value = await fetchAccounts()
})

const accountsByPlatform = computed(() => {
  const m = {}
  for (const a of accounts.value) (m[a.platform] ||= []).push(a)
  return m
})

const needsTid = computed(() =>
  form.targets.some(t => t.platform === 'bilibili')
)

function addTarget(platform) {
  const list = accountsByPlatform.value[platform] || []
  if (!list.length) {
    ElMessage.warning(`先到"账号"页登录 ${platform}`)
    return
  }
  form.targets.push({ platform, account: list[0].name })
}

function removeTarget(idx) {
  form.targets.splice(idx, 1)
}

// el-upload uses :http-request to fully take over the upload — we proxy through axios
async function handleVideoUpload({ file }) {
  uploading.value = true
  uploadProgress.value = 0
  try {
    const data = await uploadFile(file, p => uploadProgress.value = p)
    form.file = data.path
    form.fileName = data.name
    ElMessage.success(`视频已上传：${data.name}`)
  } catch (e) {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleCoverUpload({ file }) {
  try {
    const data = await uploadFile(file)
    form.cover = data.path
    form.coverName = data.name
  } catch (e) {
    ElMessage.error('封面上传失败')
  }
}

function key(platform, account) { return `${platform}:${account}` }

function initProgress() {
  const m = {}
  for (const t of form.targets) {
    m[key(t.platform, t.account)] = {
      platform: t.platform,
      account: t.account,
      stage: 'pending',          // pending | adapting | uploading | done | fail
      adapted: null,             // {title, tags}
      error: null,
      result: null,
    }
  }
  progress.value = m
}

function onPublishEvent(msg) {
  const k = (msg.platform && msg.account) ? key(msg.platform, msg.account) : null

  if (msg.event === 'adapt_start' && k) progress.value[k].stage = 'adapting'
  else if (msg.event === 'adapt_done' && k) {
    progress.value[k].adapted = { title: msg.title, tags: msg.tags }
  }
  else if (msg.event === 'upload_start' && k) progress.value[k].stage = 'uploading'
  else if (msg.event === 'upload_done' && k) {
    progress.value[k].stage = msg.success ? 'done' : 'fail'
    progress.value[k].error = msg.error
  }
  else if (msg.event === 'results') {
    for (const r of msg.results) {
      const kk = key(r.platform, r.account)
      if (progress.value[kk]) progress.value[kk].result = r
    }
  }
  else if (msg.event === 'error') {
    ElMessage.error('发布失败：' + msg.message)
  }
  else if (msg.event === 'validation_failed') {
    for (const [k2, errs] of Object.entries(msg.errors || {})) {
      if (progress.value[k2]) {
        progress.value[k2].stage = 'fail'
        progress.value[k2].error = errs.join('; ')
      }
    }
  }
  else if (msg.event === 'complete') {
    publishing.value = false
    currentES?.close()
  }
}

async function submit() {
  if (!form.file || !form.title) {
    ElMessage.warning('视频和标题都必填')
    return
  }
  if (!form.targets.length) {
    ElMessage.warning('至少选一个发布目标')
    return
  }
  publishing.value = true
  initProgress()
  try {
    const payload = {
      file: form.file,
      title: form.title,
      description: form.description,
      tags: form.tags.split(',').map(s => s.trim()).filter(Boolean),
      cover: form.cover || null,
      targets: form.targets,
      extras: form.extras,
      use_ai: form.use_ai,
      dry_run: form.dry_run,
    }
    const { task_id } = await startPublish(payload)
    currentES = subscribePublish(task_id, onPublishEvent)
  } catch (e) {
    publishing.value = false
    ElMessage.error(e.response?.data?.detail || '发布启动失败')
  }
}

function stageLabel(s) {
  return ({
    pending: '等待中', adapting: 'AI 改写中', uploading: '上传中',
    done: '✅ 完成', fail: '❌ 失败',
  })[s] || s
}
function stageTag(s) {
  return ({
    pending: 'info', adapting: 'warning', uploading: 'primary',
    done: 'success', fail: 'danger',
  })[s] || 'info'
}

const progressList = computed(() => Object.values(progress.value))
</script>

<template>
  <div class="publish">
    <h2>发布</h2>

    <el-form label-position="top" class="form" :disabled="publishing">
      <el-form-item label="视频文件" required>
        <el-upload :http-request="handleVideoUpload" :show-file-list="false" drag
                   accept="video/*" :disabled="uploading || publishing">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div v-if="form.fileName" class="filename">已选：{{ form.fileName }}</div>
          <div v-else class="hint">拖拽或点击选择视频</div>
        </el-upload>
        <el-progress v-if="uploading" :percentage="Math.round(uploadProgress * 100)" :stroke-width="6" />
      </el-form-item>

      <el-form-item>
        <template #label>
          <span>母版标题</span>
          <el-button size="small" link type="primary" @click="aiOpen = true" style="margin-left: 8px">
            <el-icon><MagicStick /></el-icon>&nbsp;AI 生成母版
          </el-button>
        </template>
        <el-input v-model="form.title" />
      </el-form-item>

      <el-form-item label="母版简介">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>

      <el-form-item label="母版标签（逗号分隔）">
        <el-input v-model="form.tags" placeholder="标签1,标签2,标签3" />
      </el-form-item>

      <el-alert type="info" :closable="false" style="margin-bottom: 16px">
        母版是你的原始文案。发布时各平台的 AI adapter 会基于此重新改写
        （抖音强钩子 / B站长描述 / 小红书 emoji / 视频号正经）。
      </el-alert>

      <el-form-item label="封面（可选）">
        <el-upload :http-request="handleCoverUpload" :show-file-list="false"
                   accept="image/*" :disabled="publishing">
          <el-button>选择封面</el-button>
          <span v-if="form.coverName" class="filename">{{ form.coverName }}</span>
        </el-upload>
      </el-form-item>

      <el-form-item label="发布目标">
        <div class="target-add">
          <el-button v-for="p in platforms" :key="p.platform" size="small"
                     @click="addTarget(p.platform)">
            + {{ p.platform }}
          </el-button>
        </div>
        <div v-for="(t, i) in form.targets" :key="i" class="target-row">
          <el-tag>{{ t.platform }}</el-tag>
          <el-select v-model="t.account" placeholder="账号" size="small" style="width: 160px">
            <el-option v-for="a in accountsByPlatform[t.platform] || []"
                       :key="a.name" :label="a.name" :value="a.name" />
          </el-select>
          <el-button size="small" text type="danger" @click="removeTarget(i)">移除</el-button>
        </div>
      </el-form-item>

      <el-form-item v-if="needsTid" label="Bilibili 分区 ID (tid)">
        <el-input-number v-model="form.extras.bilibili.tid" :min="1" />
        <span class="hint">常用 tid：21=日常，171=游戏，174=自然，188=数码。</span>
      </el-form-item>

      <el-form-item>
        <el-switch v-model="form.use_ai" active-text="AI 平台风格改写" />
        &nbsp;&nbsp;
        <el-switch v-model="form.dry_run" active-text="Dry-run（仅预览，不上传）" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="publishing" @click="submit">发布</el-button>
      </el-form-item>
    </el-form>

    <el-dialog v-model="aiOpen" title="✨ AI 生成母版" width="520px">
      <el-form label-position="top">
        <el-form-item label="视频主题 / 关键信息（必填）">
          <el-input v-model="aiTopic" type="textarea" :rows="3"
                    placeholder="例如：我用 N8N 搭了一个公众号自动推送 GitHub Trending 的工作流，完整教程" />
        </el-form-item>
        <el-form-item label="风格倾向（可选）">
          <el-input v-model="aiStyle" placeholder="例如：偏教程 / 偏吐槽 / 偏故事" />
        </el-form-item>
        <el-alert type="info" :closable="false">
          AI 会生成一份通用母版（标题/简介/标签），发布时再按各平台风格改写。
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="aiOpen = false">取消</el-button>
        <el-button type="primary" :loading="aiBusy" @click="aiGenerate">生成并填入</el-button>
      </template>
    </el-dialog>

    <div v-if="progressList.length" class="results">
      <h3>进度</h3>
      <el-card v-for="p in progressList" :key="`${p.platform}:${p.account}`" class="result-card">
        <div class="result-head">
          <span>
            <el-tag>{{ p.platform }}:{{ p.account }}</el-tag>
            <el-tag :type="stageTag(p.stage)" class="stage-tag">{{ stageLabel(p.stage) }}</el-tag>
          </span>
          <a v-if="p.result?.post_url" :href="p.result.post_url" target="_blank">打开</a>
        </div>
        <div v-if="p.adapted" class="adapted">
          <div><b>改写标题</b>：{{ p.adapted.title }}</div>
          <div v-if="p.adapted.tags?.length"><b>改写标签</b>：{{ p.adapted.tags.join(', ') }}</div>
        </div>
        <pre v-if="p.error" class="err">{{ p.error }}</pre>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.publish { max-width: 800px; }
.form { margin-top: 8px; }
.upload-icon { font-size: 36px; color: var(--el-text-color-placeholder); }
.filename { color: var(--el-color-success); margin-top: 4px; }
.target-add { margin-bottom: 8px; }
.target-add .el-button { margin-right: 6px; }
.target-row { display: flex; gap: 8px; align-items: center; padding: 4px 0; }
.hint { margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px; }
.results { margin-top: 24px; }
.result-card { margin-bottom: 12px; }
.result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.stage-tag { margin-left: 8px; }
.adapted { font-size: 13px; padding: 6px 0; color: var(--el-text-color-regular); }
.err { color: var(--el-color-danger); font-size: 12px; background: var(--el-fill-color-light); padding: 8px; border-radius: 4px; }
</style>
