import test from 'node:test'
import assert from 'node:assert/strict'

const assetImport = await import('../../../web/src/utils/asset-import.js').catch(() => ({}))

test('导入预览把可导入、跳过、错误行合并并按原 CSV 行号排序', () => {
  assert.equal(typeof assetImport.buildAssetImportPreviewRows, 'function')

  const rows = assetImport.buildAssetImportPreviewRows({
    ok_rows: [{ line: 4, asset_no: 'A-OK', name: '可用资产' }],
    skipped_rows: [{ line: 3, asset_no: 'A-SKIP', reason: '编号已存在，已跳过' }],
    error_rows: [{ line: 2, asset_no: 'A-ERR', reason: '状态无效: 未知' }],
  })

  assert.deepEqual(rows, [
    { line: 2, asset_no: 'A-ERR', name: '', outcome: '错误', reason: '状态无效: 未知' },
    { line: 3, asset_no: 'A-SKIP', name: '', outcome: '跳过', reason: '编号已存在，已跳过' },
    { line: 4, asset_no: 'A-OK', name: '可用资产', outcome: '可导入', reason: '校验通过' },
  ])
})

test('失败行 CSV 带固定列、正确转义，并阻止表格公式注入', () => {
  assert.equal(typeof assetImport.buildAssetImportErrorCsv, 'function')

  const csv = assetImport.buildAssetImportErrorCsv([
    { line: 7, asset_no: '=HYPERLINK("bad")', reason: '状态,错误\n请检查' },
  ])

  assert.equal(
    csv,
    '\ufeff行号,资产编号,失败原因\r\n7,"\'=HYPERLINK(""bad"")","状态,错误\n请检查"\r\n',
  )
})

test('没有可导入行时确认写库保持禁用', () => {
  assert.equal(typeof assetImport.canCommitAssetImport, 'function')
  assert.equal(assetImport.canCommitAssetImport({ ok: 0, errors: 3 }), false)
  assert.equal(assetImport.canCommitAssetImport({ ok: 1, errors: 3 }), true)
})

test('写库请求进行中不允许取消或关闭预览', () => {
  assert.equal(typeof assetImport.canCloseAssetImport, 'function')
  assert.equal(assetImport.canCloseAssetImport(false), true)
  assert.equal(assetImport.canCloseAssetImport(true), false)
})
