<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchPlatforms, fetchAccounts, doPublish } from '../api.js'

const platforms = ref([])
const accounts = ref([])

const form = ref({
  file: '',
  title: '',
  description: '',
  tags: '',
  cover: '',
  use_ai: true,
  dry_run: false,
  targets: [],                        // [{platform, account}]
  extras: { bilibili: { tid: 21 } },  // {platform: {key: value}}
})

const results = ref([])
const busy = ref(false)

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
  form.value.targets.some(t => t.platform === 'bilibili')
)

function addTarget(platform) {
  const list = accountsByPlatform.value[platform] || []
  if (!list.length) {
    ElMessage.warning(`先到"账号"页登录 ${platform}`)
    return
  }
  form.value.targets.push({ platform, account: list[0].name })
}

function removeTarget(idx) {
  form.value.targets.splice(idx, 1)
}

async function submit() {
  if (!form.value.file || !form.value.title) {
    ElMessage.warning('视频路径和标题都必填')
    return
  }
  if (!form.value.targets.length) {
    ElMessage.warning('至少选一个发布目标')
    return
  }
  busy.value = true
  try {
    const payload = {
      file: form.value.file,
      title: form.value.title,
      description: form.value.description,
      tags: form.value.tags.split(',').map(s => s.trim()).filter(Boolean),
      cover: form.value.cover || null,
      targets: form.value.targets,
      extras: form.value.extras,
      use_ai: form.value.use_ai,
      dry_run: form.value.dry_run,
    }
    const data = await doPublish(payload)
    results.value = data.results
    ElMessage.success('已提交')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发布失败')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="publish">
    <h2>发布</h2>

    <el-form label-position="top" class="form">
      <el-form-item label="视频文件路径（服务端可访问的绝对路径）" required>
        <el-input v-model="form.file" placeholder="/path/to/video.mp4" />
      </el-form-item>

      <el-form-item label="母版标题" required>
        <el-input v-model="form.title" />
      </el-form-item>

      <el-form-item label="母版简介">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>

      <el-form-item label="母版标签（逗号分隔）">
        <el-input v-model="form.tags" placeholder="标签1,标签2,标签3" />
      </el-form-item>

      <el-form-item label="封面路径（可选）">
        <el-input v-model="form.cover" />
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
        <el-button type="primary" :loading="busy" @click="submit">发布</el-button>
      </el-form-item>
    </el-form>

    <div v-if="results.length" class="results">
      <h3>结果</h3>
      <el-card v-for="r in results" :key="`${r.platform}:${r.account}`" class="result-card">
        <div class="result-head">
          <el-tag :type="r.success ? 'success' : 'danger'">{{ r.platform }}:{{ r.account }}</el-tag>
          <a v-if="r.post_url" :href="r.post_url" target="_blank">查看</a>
        </div>
        <pre v-if="r.error" class="err">{{ r.error }}</pre>
        <pre v-else>{{ JSON.stringify(r.raw, null, 2) }}</pre>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.publish { max-width: 800px; }
.form { margin-top: 8px; }
.target-add { margin-bottom: 8px; }
.target-add .el-button { margin-right: 6px; }
.target-row { display: flex; gap: 8px; align-items: center; padding: 4px 0; }
.hint { margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px; }
.results { margin-top: 24px; }
.result-card { margin-bottom: 12px; }
.result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.err { color: var(--el-color-danger); }
pre { font-size: 12px; background: var(--el-fill-color-light); padding: 8px; border-radius: 4px; overflow: auto; }
</style>
