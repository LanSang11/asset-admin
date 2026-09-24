import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import * as assetQr from '../../../web/src/utils/asset-qr.js'
import { GOOGLE_AUTHENTICATOR_DOWNLOADS } from '../../../web/src/constants/authenticator-apps.js'

const { assetScanPath, assetScanUrl } = assetQr

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('资产码是本站 /q/ 网址，便于手机相机打开', () => {
  assert.equal(assetScanPath('AST001'), '/q/AST001')
  assert.equal(assetScanPath('A 1'), '/q/A%201')
  assert.equal(assetScanPath('A%B'), '/q/A%25B')
  assert.equal(assetScanPath(''), '')
  assert.equal(assetScanUrl('AST001', 'https://asset.example.com'), 'https://asset.example.com/q/AST001')
  assert.equal(assetScanUrl('AST001', 'https://asset.example.com/'), 'https://asset.example.com/q/AST001')
})

test('扫码动作只为在用资产生成并携带编号与 ID 的角色路由', () => {
  assert.equal(typeof assetQr.assetActionLocation, 'function')
  assert.deepEqual(
    assetQr.assetActionLocation('repair', { id: 7, asset_no: 'NB-01', status: 1 }, 'admin'),
    {
      path: '/business/repair',
      query: { asset_id: '7', asset_no: 'NB-01' },
    }
  )
  assert.deepEqual(
    assetQr.assetActionLocation('transfer', { id: 7, asset_no: 'NB-01', status: 1 }, 'work'),
    {
      path: '/work/transfer',
      query: { asset_id: '7', asset_no: 'NB-01' },
    }
  )
  assert.equal(
    assetQr.assetActionLocation('repair', { id: 7, asset_no: 'NB-01', status: 4 }, 'work'),
    null
  )
  assert.equal(
    assetQr.assetActionLocation('delete', { id: 7, asset_no: 'NB-01', status: 1 }, 'admin'),
    null
  )
})

test('扫码动作按精确 API、角色和本人资产范围显隐', () => {
  assert.equal(typeof assetQr.canUseScanAction, 'function')
  const asset = { id: 7, asset_no: 'NB-01', status: 1 }
  const repairApi = ['post/api/v1/asset-repair/apply']
  const transferApi = ['post/api/v1/asset-transfer/apply']

  assert.equal(
    assetQr.canUseScanAction('repair', asset, {
      accessApis: repairApi,
      portal: 'work',
      hasActiveEmployee: true,
    }),
    true
  )
  assert.equal(
    assetQr.canUseScanAction('repair', asset, { accessApis: [], portal: 'admin' }),
    false
  )
  assert.equal(
    assetQr.canUseScanAction('transfer', asset, {
      accessApis: transferApi,
      portal: 'work',
      ownAssetIds: [8],
      hasActiveEmployee: true,
    }),
    false
  )
  assert.equal(
    assetQr.canUseScanAction('transfer', asset, {
      accessApis: transferApi,
      portal: 'work',
      ownAssetIds: [7],
      hasActiveEmployee: true,
    }),
    true
  )
  assert.equal(
    assetQr.canUseScanAction('transfer', asset, {
      accessApis: transferApi,
      portal: 'admin',
      hasActiveEmployee: true,
    }),
    true
  )
  assert.equal(
    assetQr.canUseScanAction('transfer', { ...asset, status: 3 }, {
      accessApis: transferApi,
      portal: 'admin',
      hasActiveEmployee: true,
    }),
    false
  )
  assert.equal(
    assetQr.canUseScanAction('repair', asset, {
      accessApis: repairApi,
      portal: 'admin',
      hasActiveEmployee: false,
    }),
    false
  )
})

test('扫码页使用已解码路由值、精确查询与请求序号', () => {
  const source = read('web/src/views/scan/index.vue')
  assert.doesNotMatch(source, /decodeURIComponent\s*\(/)
  assert.match(source, /let\s+loadRequestId\s*=\s*0/)
  assert.match(source, /\+\+loadRequestId/)
  assert.match(source, /api\.getAssetByNo\s*\(/)
  assert.match(source, /api\.getAssetActionContext\s*\(/)
})

test('扫码带入页按 ID 精确复核，不依赖模糊分页结果', () => {
  for (const path of [
    'web/src/views/business/repair/index.vue',
    'web/src/views/business/transfer/index.vue',
  ]) {
    const source = read(path)
    assert.match(source, /api\.getAssetById\s*\(/, path)
    assert.match(source, /api\.getAssetActionContext\s*\(/, path)
    assert.match(source, /const\s+hasActiveEmployee\s*=\s*ref\(false\)/, path)
    assert.match(source, /hasActiveEmployee\.value\s*&&\s*hasApi\(/, path)
  }

  const mine = read('web/src/views/work/my-assets/index.vue')
  assert.match(mine, /const\s+hasActiveEmployee\s*=\s*ref\(false\)/)
  assert.match(mine, /hasActiveEmployee\.value\s*&&\s*hasApi\(/)
})

test('目标页只接受当前可见列表中编号与 ID 同时匹配的扫码资产', () => {
  assert.equal(typeof assetQr.resolveScannedAsset, 'function')
  const visibleAssets = [
    { id: 7, asset_no: 'NB-01', name: 'ThinkPad', status: 1 },
    { id: 8, asset_no: 'NB-02', name: '显示器', status: 1 },
  ]

  assert.deepEqual(
    assetQr.resolveScannedAsset(visibleAssets, { asset_id: '7', asset_no: 'NB-01' }),
    visibleAssets[0]
  )
  assert.equal(
    assetQr.resolveScannedAsset(visibleAssets, { asset_id: '7', asset_no: 'NB-02' }),
    null
  )
  assert.equal(
    assetQr.resolveScannedAsset(visibleAssets, { asset_id: '99', asset_no: 'NB-01' }),
    null
  )
})

test('闲置、维修、报废和未知状态都有中文白话提示', () => {
  assert.equal(typeof assetQr.scanAssetStatusNotice, 'function')
  assert.equal(assetQr.scanAssetStatusNotice(1), '')
  assert.equal(assetQr.scanAssetStatusNotice(2), '这台资产当前处于闲置状态，暂不能发起报修或调拨。')
  assert.equal(assetQr.scanAssetStatusNotice(3), '这台资产正在维修中，请等待维修完成后再操作。')
  assert.equal(assetQr.scanAssetStatusNotice(4), '这台资产已经报废，只能查看信息，不能发起报修或调拨。')
  assert.equal(assetQr.scanAssetStatusNotice(99), '这台资产的状态异常，请联系管理员核对后再操作。')
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
