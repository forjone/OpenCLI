<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Loading } from '@element-plus/icons-vue'
import { fetchPlatforms, fetchAccounts, startLogin, subscribeLogin } from '../api.js'

const platforms = ref([])
const accounts = ref([])

// Login dialog
const dlgOpen = ref(false)
const dlgPlatform = ref('')
const dlgAccount = ref('')
const dlgStatus = ref('idle')         // idle | waiting | scanned | done | error
const dlgQrUrl = ref('')
let currentES = null

const grouped = computed(() => {
  const out = {}
  for (const p of platforms.value) out[p.platform] = []
  for (const a of accounts.value) (out[a.platform] ||= []).push(a)
  return out
})

onMounted(async () => {
  platforms.value = await fetchPlatforms()
  accounts.value = await fetchAccounts()
})

function openLogin(platform) {
  dlgPlatform.value = platform
  dlgAccount.value = ''
  dlgStatus.value = 'idle'
  dlgQrUrl.value = ''
  dlgOpen.value = true
}

const isBili = computed(() => dlgPlatform.value === 'bilibili')

async function beginLogin() {
  if (!dlgAccount.value) {
    ElMessage.warning('请填写账号名')
    return
  }
  if (isBili.value) {
    // biliup runs as an interactive CLI subprocess and prints its QR to stdout.
    // We don't have a clean way to stream that through the browser yet; tell
    // the user to use the CLI for this one.
    ElMessage.warning('B 站登录需要在终端运行：crosspost login --platform bilibili --account ' + dlgAccount.value)
    return
  }
  dlgStatus.value = 'waiting'
  try {
    const { task_id } = await startLogin(dlgPlatform.value, dlgAccount.value)
    currentES = subscribeLogin(task_id, onLoginEvent)
  } catch (e) {
    dlgStatus.value = 'error'
    ElMessage.error('启动登录失败')
  }
}

function onLoginEvent(msg) {
  if (msg.event === 'qrcode') {
    // Backend forwards the uploader's qrcode_callback payload verbatim.
    // All Playwright-based platforms send {image_path, image_data_url}.
    const p = msg.payload || {}
    dlgQrUrl.value = p.image_data_url || ''
  } else if (msg.event === 'done') {
    dlgStatus.value = msg.success ? 'done' : 'error'
    if (msg.success) {
      ElMessage.success('登录成功')
      fetchAccounts().then(a => accounts.value = a)
    } else {
      ElMessage.error('登录失败')
    }
    currentES?.close()
  } else if (msg.event === 'error' || msg.event === 'timeout') {
    dlgStatus.value = 'error'
    ElMessage.error(msg.message || '登录超时')
    currentES?.close()
  }
}

function closeDlg() {
  currentES?.close()
  dlgOpen.value = false
}
</script>

<template>
  <div>
    <h2>账号管理</h2>
    <p class="hint">每个平台可以保存多个账号，每个账号对应一份独立的 cookie 文件。</p>

    <el-row :gutter="16">
      <el-col :span="6" v-for="p in platforms" :key="p.platform">
        <el-card class="platform-card">
          <template #header>
            <div class="card-header">
              <span class="platform-name">{{ p.platform }}</span>
              <el-button type="primary" size="small" @click="openLogin(p.platform)">+ 添加账号</el-button>
            </div>
          </template>
          <div v-if="!grouped[p.platform]?.length" class="empty">暂无账号</div>
          <div v-for="a in grouped[p.platform]" :key="a.name" class="acct-row">
            <el-icon><User /></el-icon>
            <span>{{ a.name }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dlgOpen" :title="`登录 ${dlgPlatform}`" width="420px" @close="closeDlg">
      <el-form label-position="top" v-if="dlgStatus === 'idle'">
        <el-form-item label="账号别名（仅本地标识，可任意取）">
          <el-input v-model="dlgAccount" placeholder="如 main、work_a 等" />
        </el-form-item>
        <el-alert v-if="isBili" type="warning" :closable="false">
          B站登录走 biliup 命令行，请改用：
          <code>crosspost login --platform bilibili --account {{ dlgAccount || '<name>' }}</code>
        </el-alert>
      </el-form>

      <div v-else class="qr-area">
        <div v-if="dlgStatus === 'waiting' && !dlgQrUrl">
          <el-icon class="spin"><Loading /></el-icon>
          <p>正在准备二维码…</p>
        </div>
        <img v-if="dlgQrUrl" :src="dlgQrUrl" class="qr-img" />
        <p v-if="dlgStatus === 'waiting' && dlgQrUrl">请用 {{ dlgPlatform }} APP 扫码登录</p>
        <p v-if="dlgStatus === 'done'" class="ok">✅ 登录成功</p>
        <p v-if="dlgStatus === 'error'" class="err">❌ 登录失败</p>
      </div>

      <template #footer>
        <el-button @click="closeDlg">关闭</el-button>
        <el-button v-if="dlgStatus === 'idle'" type="primary" @click="beginLogin">开始</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.hint { color: var(--el-text-color-secondary); margin-bottom: 16px; }
.platform-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.platform-name { font-weight: 600; text-transform: capitalize; }
.empty { color: var(--el-text-color-placeholder); text-align: center; padding: 12px 0; }
.acct-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.qr-area { text-align: center; padding: 16px 0; }
.qr-img { width: 220px; height: 220px; }
.ok { color: var(--el-color-success); }
.err { color: var(--el-color-danger); }
.spin { font-size: 32px; animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }
</style>
