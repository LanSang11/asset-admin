import { h } from 'vue'
import { Icon } from '@iconify/vue/offline'
import { NIcon } from 'naive-ui'
import SvgIcon from '@/components/icon/SvgIcon.vue'
import { resolveLocalIcon } from './local-icon-data'

/**
 * 统一菜单/业务图标为 Iconify 可识别格式。
 *
 * 历史脏数据：`icon-mdi:briefcase`（错误地把 unplugin 前缀写进库）→ `mdi:briefcase`
 * 合法集合：`icon-park-outline:workbench` 本身就是 Iconify 集合名，**禁止**去掉 `icon-`。
 */
export function normalizeIconName(icon) {
  if (!icon || typeof icon !== 'string') return icon
  const raw = icon.trim()
  if (!raw) return raw
  if (raw === 'user') return 'mdi:account-circle-outline'

  // 合法 Iconify：icon-park / icon-park-outline / icon-park-solid / icon-park-twotone
  if (/^icon-park(-outline|-solid|-twotone)?:/i.test(raw)) {
    return raw
  }

  // 错误写法：icon-mdi:xxx / icon-carbon:xxx → mdi:xxx / carbon:xxx
  // 仅当去掉 icon- 后集合名不是 park* 时才剥离（避免拆坏工作台）
  const wrongUnplugin = raw.match(/^icon-([a-z0-9-]+):(.+)$/i)
  if (wrongUnplugin) {
    const coll = wrongUnplugin[1]
    if (!/^park/i.test(coll)) {
      return `${coll}:${wrongUnplugin[2]}`
    }
  }

  // 已是 collection:name
  if (raw.includes(':')) return raw

  // mdi-xxx / material-symbols-xxx → prefix:name
  const known = [
    'material-symbols',
    'icon-park-outline',
    'icon-park-solid',
    'icon-park-twotone',
    'icon-park',
    'ant-design',
    'mingcute',
    'carbon',
    'tabler',
    'solar',
    'clarity',
    'mdi',
    'ph',
  ]
  for (const prefix of known) {
    if (raw.startsWith(`${prefix}-`)) {
      return `${prefix}:${raw.slice(prefix.length + 1)}`
    }
  }

  return raw
}

export function renderIcon(icon, props = { size: 12 }) {
  const name = normalizeIconName(icon)
  const iconData = resolveLocalIcon(name)
  return () => h(NIcon, props, { default: () => h(Icon, { icon: iconData }) })
}

export function renderCustomIcon(icon, props = { size: 12 }) {
  return () => h(NIcon, props, { default: () => h(SvgIcon, { icon }) })
}
