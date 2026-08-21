// 验证通知 route 白名单正则：正常站内路径应放行，外部/协议路径应拦截
const re = /^\/(?!\/|\\|[:?#])/
const cases = [
  ['/business/approval', true],
  ['/business/asset-use', true],
  ['/business/employee', true],
  ['/workbench', true],
  ['/profile?x=1', true],
  ['//evil.com', false],
  ['/\\evil.com', false],
  ['javascript:alert(1)', false],
  ['http://evil.com', false],
  ['https://evil.com', false],
  ['', false],
]
let failed = 0
for (const [input, expect] of cases) {
  const got = re.test(input)
  const mark = got === expect ? 'PASS' : 'FAIL'
  if (got !== expect) failed++
  console.log(`${mark}: ${JSON.stringify(input)} -> ${got} (expect ${expect})`)
}
console.log(failed === 0 ? 'ALL PASS' : `${failed} FAILURES`)
process.exit(failed === 0 ? 0 : 1)
