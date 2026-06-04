<script setup>
import { ref, onMounted } from 'vue'
import { fetchSettings } from '../api.js'

const cfg = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    cfg.value = await fetchSettings()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings" v-loading="loading">
    <h2>设置</h2>
    <p class="hint">
      目前 AI 配置只在 <code>conf.py</code> 和环境变量中。这里是只读视图，
      改完配置后重启后端 (uvicorn) 才生效。
    </p>

    <el-card v-if="cfg">
      <template #header><b>AI / LLM</b></template>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="API Key">
          <el-tag :type="cfg.has_api_key ? 'success' : 'danger'">
            {{ cfg.has_api_key ? '已设置' : '未设置' }}
          </el-tag>
          <span class="kv-hint">环境变量 <code>ANTHROPIC_API_KEY</code></span>
        </el-descriptions-item>
        <el-descriptions-item label="模型">
          <code>{{ cfg.model }}</code>
          <span class="kv-hint">在 conf.py 中 <code>LLM_MODEL</code></span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="cfg" class="mt">
      <template #header><b>平台 Prompt 模板</b></template>
      <p class="hint">每个平台一份 markdown，控制 AI 怎么把"母版"改写成该平台的风格。直接编辑这些文件即可。</p>
      <el-table :data="cfg.prompt_files" stripe>
        <el-table-column prop="platform" label="平台" width="140" />
        <el-table-column prop="path" label="路径" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.exists ? 'success' : 'danger'" size="small">
              {{ row.exists ? 'OK' : '缺失' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="cfg" class="mt">
      <template #header><b>本地路径</b></template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="账号 cookie">
          <code>{{ cfg.cookies_dir }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="上传/数据">
          <code>{{ cfg.data_dir }}</code>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="mt">
      <template #header><b>怎么改</b></template>
      <pre class="snippet">
# 1. 改模型 / 路径：编辑 conf.py
LLM_MODEL = "claude-opus-4-8"        # 更强但更贵
COOKIES_DIR = BASE_DIR / "cookies"

# 2. 设 API key（任一方式）
export ANTHROPIC_API_KEY=sk-...      # shell
# 或写在 .env 由 uvicorn 加载

# 3. 改平台风格：编辑 adapters/prompts/{douyin,bilibili,xiaohongshu,tencent}.md
</pre>
    </el-card>
  </div>
</template>

<style scoped>
.settings { max-width: 760px; }
.hint { color: var(--el-text-color-secondary); font-size: 13px; }
.mt { margin-top: 16px; }
.kv-hint { color: var(--el-text-color-secondary); margin-left: 10px; font-size: 12px; }
code { background: var(--el-fill-color-light); padding: 1px 6px; border-radius: 3px; font-family: ui-monospace, monospace; }
.snippet { background: var(--el-fill-color-light); padding: 12px; border-radius: 4px; font-size: 12px; line-height: 1.6; overflow: auto; }
</style>
