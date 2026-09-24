export const PASSWORD_RULE_TEXT = '密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号'

const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,32}$/

export function isStrongPassword(value) {
  return typeof value === 'string' && PASSWORD_PATTERN.test(value)
}
