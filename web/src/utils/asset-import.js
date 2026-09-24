function previewRow(row, outcome, defaultReason) {
  return {
    line: Number(row?.line || 0),
    asset_no: String(row?.asset_no || ''),
    name: String(row?.name || ''),
    outcome,
    reason: String(row?.reason || defaultReason),
  }
}

export function buildAssetImportPreviewRows(data = {}) {
  const rows = [
    ...(data.error_rows || []).map((row) => previewRow(row, '错误', '校验失败')),
    ...(data.skipped_rows || []).map((row) => previewRow(row, '跳过', '已跳过')),
    ...(data.ok_rows || []).map((row) => previewRow(row, '可导入', '校验通过')),
  ]
  return rows.sort((a, b) => a.line - b.line)
}

function guardSpreadsheetFormula(value) {
  return /^[=+\-@]/.test(value) ? `'${value}` : value
}

function csvCell(value) {
  const guarded = guardSpreadsheetFormula(String(value ?? ''))
  return /[",\r\n]/.test(guarded) ? `"${guarded.replaceAll('"', '""')}"` : guarded
}

export function buildAssetImportErrorCsv(errorRows = []) {
  const lines = ['行号,资产编号,失败原因']
  for (const row of errorRows) {
    lines.push([row?.line || '', row?.asset_no || '', row?.reason || ''].map(csvCell).join(','))
  }
  return `\ufeff${lines.join('\r\n')}\r\n`
}

export function canCommitAssetImport(data = {}) {
  return Number(data.ok || 0) > 0
}

export function canCloseAssetImport(loading = false) {
  return !loading
}
