import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import { getOrCreateClientId } from './clientId'
import { loadVenue } from './venue'

const clientId = getOrCreateClientId()
console.log('client_id:', clientId)

document.ondblclick = function (e) {
  e.preventDefault()
}

// Arena names/colors fill in when this resolves; labels show raw ids until then
void loadVenue()

createApp(App).mount('#app')
