<script setup>
import { ref, onMounted } from 'vue'
import { fetchPosts } from '../api.js'

const posts = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    posts.value = await fetchPosts(100)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="head">
      <h2>发布历史</h2>
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
    </div>

    <el-table :data="posts" stripe v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column prop="platform" label="平台" width="110">
        <template #default="{ row }"><el-tag size="small">{{ row.platform }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="account" label="账号" width="110" />
      <el-table-column prop="title" label="标题" />
      <el-table-column label="结果" width="100">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'" size="small">
            {{ row.success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="链接" width="80">
        <template #default="{ row }">
          <a v-if="row.post_url" :href="row.post_url" target="_blank">打开</a>
          <span v-else>—</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
</style>
