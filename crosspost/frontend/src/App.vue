<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <el-container style="height: 100vh">
    <el-header class="topbar">
      <div class="brand">crosspost</div>
      <el-menu mode="horizontal" :default-active="route.path" router class="nav">
        <el-menu-item index="/publish">发布</el-menu-item>
        <el-menu-item index="/accounts">账号</el-menu-item>
        <el-menu-item index="/history">历史</el-menu-item>
      </el-menu>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
.topbar {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid var(--el-border-color-light);
}
.brand {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 1px;
}
.nav {
  border-bottom: none !important;
  flex: 1;
}
</style>
