import { createApp } from 'vue'
import ProductShell from './ProductShell.vue'
import { t, statusText, message } from './i18n.js'
import './style.css'
import './product.css'

const app = createApp(ProductShell)
Object.assign(app.config.globalProperties, { $t: t, $status: statusText, $message: message })
app.mount('#app')
