const PREF_PREFIX = 'tbl-col'

function uniqueStrings(values) {
  return [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))]
}

export function getColumnPrefStorage() {
  try {
    if (typeof globalThis !== 'undefined' && globalThis.localStorage) {
      return globalThis.localStorage
    }
  } catch {
    // Safari 隐私模式等会在访问 localStorage 时抛错
  }
  return null
}

export function buildTableColumnPrefKey({ userId, routePath, tableId } = {}) {
  if (userId == null || userId === '') return null
  const route = String(routePath || '').replace(/\/+$/, '') || '/'
  const table = String(tableId || 'default').trim() || 'default'
  return `${PREF_PREFIX}:${userId}:${route}:${table}`
}

export function columnToggleKey(column) {
  if (!column || column.type) return ''
  if (column.key == null || column.key === '') return ''
  return String(column.key)
}

export function listSettingColumns(columns = [], lockedKeys = []) {
  const locked = new Set(uniqueStrings(lockedKeys))
  const seen = new Set()
  const items = []
  for (const column of columns) {
    const key = columnToggleKey(column)
    if (!key || seen.has(key) || typeof column.title !== 'string') continue
    seen.add(key)
    items.push({
      key,
      title: column.title,
      locked: locked.has(key),
    })
  }
  return items
}

export function sanitizeHiddenKeys(hiddenKeys = [], columns = [], lockedKeys = []) {
  const locked = new Set(uniqueStrings(lockedKeys))
  const allowed = new Set(
    (columns || [])
      .map((column) => columnToggleKey(column))
      .filter((key) => key && !locked.has(key))
  )
  return uniqueStrings(hiddenKeys).filter((key) => allowed.has(key))
}

export function filterVisibleColumns(columns = [], hiddenKeys = [], lockedKeys = []) {
  const locked = new Set(uniqueStrings(lockedKeys))
  const hidden = new Set(uniqueStrings(hiddenKeys))
  return (columns || []).filter((column) => {
    const key = columnToggleKey(column)
    if (!key || locked.has(key)) return true
    return !hidden.has(key)
  })
}

export function applyColumnVisibility(hiddenKeys, key, visible, lockedKeys = []) {
  const locked = new Set(uniqueStrings(lockedKeys))
  const next = new Set(uniqueStrings(hiddenKeys))
  const columnKey = String(key || '').trim()
  if (!columnKey || locked.has(columnKey) || visible) {
    next.delete(columnKey)
    return [...next]
  }
  next.add(columnKey)
  return [...next]
}

export function readHiddenKeys(storage, prefKey) {
  if (!storage || !prefKey) return []
  try {
    const raw = storage.getItem(prefKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return uniqueStrings(parsed)
  } catch {
    return []
  }
}

export function writeHiddenKeys(storage, prefKey, hiddenKeys) {
  if (!storage || !prefKey) return false
  try {
    const keys = uniqueStrings(hiddenKeys)
    if (!keys.length) {
      storage.removeItem(prefKey)
      return true
    }
    storage.setItem(prefKey, JSON.stringify(keys))
    return true
  } catch {
    return false
  }
}
