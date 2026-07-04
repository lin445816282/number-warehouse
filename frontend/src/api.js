import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'

const BASE = '/number-warehouse'

const api = {
  async get(path) {
    const res = await fetch(BASE + path)
    return res.json()
  },
  async post(path, data) {
    const res = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    return res.json()
  },
  async put(path, data) {
    const res = await fetch(BASE + path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    return res.json()
  },
  async del(path) {
    const res = await fetch(BASE + path, { method: 'DELETE' })
    return res.json()
  },
}

export default api
export { BASE }
