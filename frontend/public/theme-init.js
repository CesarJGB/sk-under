/* Inicializa la apariencia antes del primer pintado, sin scripts inline (CSP script-src 'self'). */
(function () {
  var key = 'sk-under.theme'
  var preference = 'system'
  try {
    var stored = window.localStorage.getItem(key)
    if (stored === 'light' || stored === 'dark' || stored === 'system') preference = stored
  } catch (error) {
    preference = 'system'
  }
  var systemDark = false
  try {
    systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch (error) {
    systemDark = false
  }
  var theme = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
  var meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0C120F' : '#112820')
})()