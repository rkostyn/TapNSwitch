import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'

document.ondblclick = function (e) {
  e.preventDefault()
}

createApp(App).mount('#app')
