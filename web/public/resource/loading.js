function addThemeColorCssVars() {
  const key = '__THEME_COLOR__'
  const defaultColor = '#F4511E'
  let themeColor = defaultColor

  try {
    themeColor = window.localStorage.getItem(key) || defaultColor
  } catch {
    themeColor = defaultColor
  }

  const isSupportedColor =
    typeof CSS !== 'undefined' &&
    typeof CSS.supports === 'function' &&
    CSS.supports('color', themeColor)

  if (!isSupportedColor) {
    themeColor = defaultColor
  }

  document.documentElement.style.setProperty('--primary-color', themeColor)
}

addThemeColorCssVars()
