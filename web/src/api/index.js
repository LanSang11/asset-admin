import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  // L2 登录滑块（公开，失败达阈值后使用）
  getSlideCaptcha: () => request.get('/base/captcha/slide', { noNeedToken: true }),
  verifySlideCaptcha: (data = {}) =>
    request.post('/base/captcha/slide/verify', data, { noNeedToken: true, silent: true }),
  getCaptchaStatus: (params = {}) =>
    request.get('/base/captcha/status', { params, noNeedToken: true, silent: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // 高危二次验证 / TOTP
  getStepUpRequirement: (params = {}) => request.get('/base/step_up/requirement', { params }),
  stepUp: (data = {}) => request.post('/base/step_up', data),
  totpSetup: () => request.post('/base/totp/setup', {}),
  totpConfirm: (data = {}) => request.post('/base/totp/confirm', data),
  totpDisable: (data = {}) => request.post('/base/totp/disable', data),
  setTotpRecoveryQuestion: (data = {}) => request.post('/base/totp/recovery-question', data),
  recoverTotp: (data = {}) => request.post('/base/totp/recover', data, { noNeedToken: true }),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}, headers = {}) => request.post('/user/create', data, { headers }),
  updateUser: (data = {}, headers = {}) => request.post('/user/update', data, { headers }),
  deleteUser: (params = {}, headers = {}) =>
    request.delete(`/user/delete`, { params, headers }),
  resetPassword: (data = {}, headers = {}) =>
    request.post(`/user/reset_password`, data, { headers }),
  resetUserTotp: (data = {}, headers = {}) => request.post('/user/reset_totp', data, { headers }),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}, headers = {}) =>
    request.delete('/role/delete', { params, headers }),
  updateRoleAuthorized: (data = {}, headers = {}) =>
    request.post('/role/authorized', data, { headers }),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}, headers = {}) =>
    request.delete('/menu/delete', { params, headers }),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}, headers = {}) =>
    request.delete('/api/delete', { params, headers }),
  refreshApi: (data = {}, headers = {}) => request.post('/api/refresh', data, { headers }),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}, headers = {}) =>
    request.delete('/dept/delete', { params, headers }),
  // auditlog / security
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  getSecurityEvents: (params = {}) => request.get('/security/events', { params }),
  getLoginEvents: (params = {}) => request.get('/security/login-events', { params }),
  getSecurityDashboard: () => request.get('/security/dashboard'),
  getSecurityTagHelp: () => request.get('/security/tag-help'),
  getSecurityUserDevices: (params = {}) => request.get('/security/user-devices', { params }),
  getSecurityRetention: () => request.get('/security/retention'),
  getSecurityPosture: (params = {}) => request.get('/security/posture', { params, silent: true }),
  getAttackAgg: (params = {}) => request.get('/security/attacks', { params }),
  getVerificationPolicies: () => request.get('/security/verification-policies'),
  updateVerificationPolicies: (data = {}, headers = {}) =>
    request.put('/security/verification-policies', data, { headers }),
  updateAcceptanceMode: (data = {}, headers = {}) =>
    request.put('/security/acceptance-mode', data, { headers }),
  getTlsStatus: () => request.get('/security/tls'),
  renewTlsCert: (headers = {}) => request.post('/security/tls/renew', {}, { headers }),
  getBlacklist: () => request.get('/base/blacklist'),
  banBlacklist: (data = {}, headers = {}) =>
    request.post('/base/blacklist', data, { headers }),
  unbanBlacklist: (params = {}, headers = {}) =>
    request.delete('/base/blacklist', { params, headers }),
  // employees（阶段2 业务）
  getEmployeeList: (params = {}) => request.get('/employee/list', { params }),
  getEmployeeById: (params = {}) => request.get('/employee/get', { params }),
  createEmployee: (data = {}) => request.post('/employee/create', data),
  updateEmployee: (data = {}) => request.post('/employee/update', data),
  deleteEmployee: (params = {}, headers = {}) =>
    request.delete('/employee/delete', { params, headers }),
  // assets（阶段2 业务）
  getAssetList: (params = {}) => request.get('/asset/list', { params }),
  getMyAssets: () => request.get('/asset/my'),
  getAssetById: (params = {}) => request.get('/asset/get', { params }),
  getAssetCategories: () => request.get('/asset/categories'),
  createAsset: (data = {}) => request.post('/asset/create', data),
  updateAsset: (data = {}) => request.post('/asset/update', data),
  deleteAsset: (params = {}, headers = {}) =>
    request.delete('/asset/delete', { params, headers }),
  // asset-use（阶段2 领用归还）
  applyAssetUse: (data = {}) => request.post('/asset-use/apply', data),
  approveAssetUse: (data = {}) => request.post('/asset-use/approve', data),
  getAssetUseList: (params = {}) => request.get('/asset-use/list', { params }),
  getAssetHistory: (params = {}) => request.get('/asset-use/history', { params }),
  applyAssetRepair: (data = {}) => request.post('/asset-repair/apply', data),
  approveAssetRepair: (data = {}) => request.post('/asset-repair/approve', data),
  completeAssetRepair: (data = {}) => request.post('/asset-repair/complete', data),
  registerAssetRepair: (data = {}) => request.post('/asset-repair/register', data),
  getAssetRepairList: (params = {}) => request.get('/asset-repair/list', { params }),
  applyAssetTransfer: (data = {}) => request.post('/asset-transfer/apply', data),
  approveAssetTransfer: (data = {}) => request.post('/asset-transfer/approve', data),
  getAssetTransferList: (params = {}) => request.get('/asset-transfer/list', { params }),
  getTransferCandidates: () => request.get('/asset-transfer/candidates'),
  startInventory: (data = {}) => request.post('/inventory/start', data),
  getInventoryList: (params = {}) => request.get('/inventory/list', { params }),
  getInventory: (params = {}) => request.get('/inventory/get', { params }),
  getInventoryLines: (params = {}) => request.get('/inventory/lines', { params }),
  countInventory: (data = {}) => request.post('/inventory/count', data),
  closeInventory: (data = {}) => request.post('/inventory/close', data),
  // notifications（阶段2 通知）
  getNotificationList: (params = {}) => request.get('/notification/list', { params, silent: true }),
  getUnreadCount: () => request.get('/notification/unread_count', { silent: true }),
  markNotificationRead: (params = {}) => request.post('/notification/read', {}, { params }),
  markAllRead: () => request.post('/notification/read_all'),
  // exports（阶段2 导出）
  exportEmployees: (params = {}) => request.get('/export/employees', { params, responseType: 'blob' }),
  exportAssets: (params = {}) => request.get('/export/assets', { params, responseType: 'blob' }),
  exportAssetUses: (params = {}) => request.get('/export/asset-uses', { params, responseType: 'blob' }),
  importAssets: (formData, commit = 0, headers = {}) =>
    request.post(`/export/import-assets?commit=${commit}`, formData, { headers }),
  // dashboard（阶段2 看板）
  getDashboardStats: () => request.get('/dashboard/stats', { silent: true }),
  // ai（四层架构第二层/阶段3）
  saveApiConfig: (data = {}) => request.post('/api-config/save', data),
  getMyApiConfig: () => request.get('/api-config/my'),
  aiChat: (data = {}) => request.post('/ai/chat', data),
  aiVision: (data = {}) => request.post('/ai/vision', data),
  askAssistant: (data = {}) => request.post('/ai/assistant/ask', data),
  uploadEmployeeAttachment: (formData) => request.post('/employee-attachment/upload', formData),
  getEmployeeAttachments: (params = {}) => request.get('/employee-attachment/list', { params }),
  deleteEmployeeAttachment: (params = {}) => request.delete('/employee-attachment/delete', { params }),
  uploadKbDoc: (formData) => request.post('/kb/upload', formData),
  seedKbBuiltin: () => request.post('/kb/seed-builtin', {}),
  getKbList: () => request.get('/kb/list'),
  askKb: (data = {}) => request.post('/kb/ask', data, { timeout: 45000 }),
  analyzeKb: () => request.post('/kb/steward/analyze', {}),
  draftKbGaps: (data = {}) => request.post('/kb/steward/draft', data, { timeout: 45000 }),
  ingestKbDraft: (data = {}) => request.post('/kb/steward/ingest', data),
  deleteKbDoc: (params = {}) => request.delete('/kb/delete', { params }),
}
