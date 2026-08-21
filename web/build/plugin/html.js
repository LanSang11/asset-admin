import dayjs from 'dayjs'
import { createHtmlPlugin } from 'vite-plugin-html'

export function configHtmlPlugin(viteEnv, isBuild) {
  const { VITE_TITLE } = viteEnv

  const htmlPlugin = createHtmlPlugin({
    minify: isBuild,
    inject: {
      data: {
        title: VITE_TITLE,
        // 构建时间戳：每次构建自动变化，用于 public 下非 hash 资源（favicon/loading.js）的缓存刷新
        buildTime: dayjs().format('YYYYMMDDHHmmss'),
      },
    },
  })
  return htmlPlugin
}
