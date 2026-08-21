import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { assetScanPath, assetScanUrl } from '../../../web/src/utils/asset-qr.js'
import { GOOGLE_AUTHENTICATOR_DOWNLOADS } from '../../../web/src/constants/authenticator-apps.js'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('资产码是本站 /q/ 网址，便于手机相机打开', () => {
  assert.equal(assetScanPath('AST001'), '/q/AST001')
  assert.equal(assetScanPath('A 1'), '/q/A%201')
  assert.equal(assetScanPath(''), '')
  assert.equal(assetScanUrl('AST001', 'https://asset.example.com'), 'https://asset.example.com/q/AST001')
  assert.equal(assetScanUrl('AST001', 'https://asset.example.com/'), 'https://asset.example.com/q/AST001')
})

test('谷歌验证器只链官方商店，不链第三方 APK', () => {
  const ios = GOOGLE_AUTHENTICATOR_DOWNLOADS.find((item) => item.id === 'ios')
  const android = GOOGLE_AUTHENTICATOR_DOWNLOADS.find((item) => item.id === 'android')
  const msIos = GOOGLE_AUTHENTICATOR_DOWNLOADS.find((item) => item.id === 'ms-ios')
  assert.match(ios.href, /^https:\/\/apps\.apple\.com\//)
  assert.match(ios.href, /id388497605/)
  assert.doesNotMatch(ios.href, /\/cn\/app\/google-authenticator/)
  assert.match(android.href, /^https:\/\/play\.google\.com\/store\/apps\/details/)
  assert.match(android.href, /com\.google\.android\.apps\.authenticator2/)
  assert.match(msIos.href, /apps\.apple\.com\/cn\/app\/microsoft-authenticator\/id983156458/)
  const blob = JSON.stringify(GOOGLE_AUTHENTICATOR_DOWNLOADS)
  assert.doesNotMatch(blob, /uptodown|apkpure|wandoujia|fir\.im/i)
})

test('绑定页和登录第二步带官方下载，资产页能出手机码', () => {
  const profile = read('web/src/views/profile/index.vue')
  const login = read('web/src/views/login/index.vue')
  const assetPage = read('web/src/views/business/asset/index.vue')
  const mine = read('web/src/views/work/my-assets/index.vue')
  const routes = read('web/src/router/routes/index.js')
  assert.match(profile, /AuthenticatorDownloadLinks/)
  assert.match(login, /AuthenticatorDownloadLinks/)
  assert.match(assetPage, /AssetQrDialog/)
  assert.match(mine, /AssetQrDialog/)
  assert.match(routes, /path:\s*['"]\/q\/:assetNo['"]/)
})
