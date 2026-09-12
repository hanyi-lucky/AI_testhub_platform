/**
 * APP自动化测试模块 - 公共工具函数
 */

// ========== 执行状态映射（任务生命周期） ==========

const EXECUTION_STATUS_MAP = {
  'pending':   { type: 'info',    text: '等待中' },
  'running':   { type: 'warning', text: '执行中' },
  'completed': { type: 'success', text: '已完成' },
  'error':     { type: 'danger',  text: '执行异常' },
  'stopped':   { type: 'info',    text: '已停止' },
  // 向后兼容旧值
  'success':   { type: 'success', text: '已完成' },
  'failed':    { type: 'danger',  text: '失败' },
}

// ========== 测试结果映射（用例通过/失败） ==========

const EXECUTION_RESULT_MAP = {
  'passed':  { type: 'success', text: '通过' },
  'failed':  { type: 'danger',  text: '失败' },
  'skipped': { type: 'warning', text: '跳过' },
}

const DEVICE_STATUS_MAP = {
  'available': { type: 'success', text: '可用' },
  'locked':    { type: 'warning', text: '已锁定' },
  'online':    { type: 'success', text: '在线' },
  'offline':   { type: 'danger',  text: '离线' },
}

/**
 * 获取执行状态的 Element Plus Tag 类型
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getExecutionStatusType(status) {
  return EXECUTION_STATUS_MAP[status]?.type || 'info'
}

/**
 * 获取执行状态的中文文本
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getExecutionStatusText(status) {
  return EXECUTION_STATUS_MAP[status]?.text || status
}

/**
 * 获取测试结果的 Element Plus Tag 类型
 * @param {string} result - 结果值 (passed/failed/skipped)
 * @returns {string}
 */
export function getResultType(result) {
  return EXECUTION_RESULT_MAP[result]?.type || 'info'
}

/**
 * 获取测试结果的中文文本
 * @param {string} result - 结果值
 * @returns {string}
 */
export function getResultText(result) {
  return EXECUTION_RESULT_MAP[result]?.text || '-'
}

/**
 * 获取综合展示的类型和文本（优先显示测试结果，其次显示任务状态）
 * 适用于列表中单列展示场景
 * @param {string} status - 任务状态
 * @param {string|null} result - 测试结果
 * @returns {{ type: string, text: string }}
 */
export function getDisplayStatus(status, result) {
  // 任务还在进行中，显示任务状态
  if (status === 'pending' || status === 'running') {
    return EXECUTION_STATUS_MAP[status]
  }
  // 任务异常，显示异常状态
  if (status === 'error') {
    return { type: 'danger', text: '执行异常' }
  }
  // 任务已停止
  if (status === 'stopped') {
    return { type: 'info', text: '已停止' }
  }
  // 任务已完成，显示测试结果
  if (result) {
    return EXECUTION_RESULT_MAP[result] || { type: 'info', text: result }
  }
  // 兜底
  return EXECUTION_STATUS_MAP[status] || { type: 'info', text: status || '-' }
}

/**
 * 获取设备状态的 Element Plus Tag 类型
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getDeviceStatusType(status) {
  return DEVICE_STATUS_MAP[status]?.type || 'info'
}

/**
 * 获取设备状态的中文文本
 * @param {string} status - 状态值
 * @returns {string}
 */
export function getDeviceStatusText(status) {
  return DEVICE_STATUS_MAP[status]?.text || status
}

// ========== 日期格式化 ==========

/**
 * 格式化日期时间（完整格式）
 * @param {string} timeStr - ISO 时间字符串
 * @returns {string}
 */
export function formatDateTime(timeStr) {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

/**
 * 格式化为相对时间（如"3分钟前"）
 * @param {string} timeStr - ISO 时间字符串
 * @returns {string}
 */
export function formatRelativeTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return Math.floor(diff / 86400000) + ' 天前'
}
