import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import { getOrCreateClientId } from './clientId'

const clientId = getOrCreateClientId()
console.log('client_id:', clientId)

document.ondblclick = function (e) {
  e.preventDefault()
}

createApp(App).mount('#app')
