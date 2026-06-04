import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/publish' },
  { path: '/accounts', component: () => import('./views/Accounts.vue'), meta: { title: '账号' } },
  { path: '/publish', component: () => import('./views/Publish.vue'), meta: { title: '发布' } },
  { path: '/history', component: () => import('./views/History.vue'), meta: { title: '历史' } },
  { path: '/settings', component: () => import('./views/Settings.vue'), meta: { title: '设置' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
