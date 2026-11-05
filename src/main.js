import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { vDigits } from './directives/digits'
import { useAuthStore } from './stores/auth'
import './assets/styles/globals.css'

const app = createApp(App)
app.use(createPinia())
app.directive('digits', vDigits)

// Restore the session before the first route resolves, so a signed-in user
// reloading on a guarded page isn't bounced to /login.
const auth = useAuthStore()
await auth.hydrate()

app.use(router)
app.mount('#app')
