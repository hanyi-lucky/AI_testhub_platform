<template>
  <div class="notification-logs">
    <!-- 搜索栏 -->
    <div class="filters">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-input v-model="searchForm.taskName" placeholder="搜索任务名称" clearable @clear="handleSearch" @keyup.enter="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-date-picker v-model="searchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" @change="handleSearch" />
        </el-col>
        <el-col :span="6">
          <el-select v-model="searchForm.status" placeholder="发送状态" clearable @change="handleSearch">
            <el-option label="全部" value="" />
            <el-option label="发送成功" value="success" />
            <el-option label="发送失败" value="failed" />
            <el-option label="待发送" value="pending" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="handleSearch"><el-icon><Search /></el-icon>查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 列表 -->
    <el-table :data="logsData" v-loading="loading" border stripe @sort-change="handleSortChange">
      <el-table-column prop="task_name" label="任务名称" min-width="150" sortable="custom" />
      <el-table-column label="任务类型" width="110">
        <template #default="{ row }">
          <el-tag type="info" size="small">{{ row.task_type_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="通知类型" width="120">
        <template #default="{ row }">
          <el-tag :type="getNotificationTypeTag(row.actual_notification_type_display)" size="small">
            {{ row.actual_notification_type_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="通知时间" width="180" sortable="custom">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="getStatusTag(row.status)" size="small">{{ row.status_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="100">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchLogs"
        @current-change="fetchLogs"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="通知详情" width="600px">
      <el-form v-if="selectedLog" label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务名称"><span>{{ selectedLog.task_name }}</span></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务类型"><span>{{ selectedLog.task_type_display }}</span></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="通知类型">
              <el-tag :type="getNotificationTypeTag(selectedLog.actual_notification_type_display)">
                {{ selectedLog.actual_notification_type_display }}
              </el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-tag :type="getStatusTag(selectedLog.status)">{{ selectedLog.status_display }}</el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="通知时间"><span>{{ formatDate(selectedLog.created_at) }}</span></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发送时间"><span>{{ selectedLog.sent_at ? formatDate(selectedLog.sent_at) : '-' }}</span></el-form-item>
          </el-col>
          <el-col :span="24" v-if="selectedLog.webhook_bot_info && (selectedLog.webhook_bot_info.type || selectedLog.webhook_bot_info.bot_type)">
            <el-form-item label="Webhook机器人">
              <el-tag size="small" type="info">{{ selectedLog.webhook_bot_info.name || '默认机器人' }}</el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="通知内容">
              <div class="content-box">
                <div v-if="parsedContent" class="parsed-content">
                  <div v-for="(item, i) in parsedContent" :key="i" class="content-row">
                    <span class="label">{{ item.label }}:</span>
                    <span class="value">{{ item.value }}</span>
                  </div>
                </div>
                <pre v-else class="raw-content">{{ selectedLog.notification_content || '-' }}</pre>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="selectedLog.error_message">
            <el-form-item label="错误信息">
              <el-alert :title="selectedLog.error_message" type="error" show-icon :closable="false" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getAppNotificationLogs } from '@/api/app-automation.js'

const loading = ref(false)
const logsData = ref([])
const detailVisible = ref(false)
const selectedLog = ref(null)

const searchForm = reactive({ taskName: '', dateRange: [], status: '' })
const pagination = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const sortParams = reactive({ prop: 'created_at', order: 'descending' })

onMounted(fetchLogs)

async function fetchLogs() {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize,
      ordering: sortParams.order === 'ascending' ? sortParams.prop : `-${sortParams.prop}`,
    }
    if (searchForm.taskName) params.search = searchForm.taskName
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.dateRange?.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    const res = await getAppNotificationLogs(params)
    logsData.value = res.data.results || []
    pagination.total = res.data.count || 0
  } catch { ElMessage.error('加载通知日志失败') }
  finally { loading.value = false }
}

function handleSearch() { pagination.currentPage = 1; fetchLogs() }
function handleReset() { searchForm.taskName = ''; searchForm.dateRange = []; searchForm.status = ''; handleSearch() }
function handleSortChange({ prop, order }) { sortParams.prop = prop; sortParams.order = order || 'descending'; fetchLogs() }
function viewDetail(row) { selectedLog.value = row; detailVisible.value = true }

function formatDate(s) { return s ? new Date(s).toLocaleString('zh-CN') : '-' }
function getStatusTag(s) { return { success: 'success', failed: 'danger', pending: 'info', sending: 'warning' }[s] || 'info' }
function getNotificationTypeTag(t) {
  if (!t || t === '-') return 'info'
  if (t.includes('邮箱')) return ''
  if (t.includes('机器人') || t.includes('Webhook')) return 'primary'
  return 'info'
}

const parsedContent = computed(() => {
  if (!selectedLog.value?.notification_content) return null
  const content = selectedLog.value.notification_content
  try {
    const json = JSON.parse(content)
    let text = ''
    if (json.markdown?.content) text = json.markdown.content
    else if (json.markdown?.text) text = json.markdown.text
    else if (json.card?.elements?.[0]?.text?.content) text = json.card.elements[0].text.content
    if (text) {
      return text.split('\n').filter(l => l.trim() && !l.includes('**')).map(l => {
        const idx = l.indexOf(':')
        return idx > 0 ? { label: l.substring(0, idx).trim(), value: l.substring(idx + 1).trim() } : null
      }).filter(Boolean)
    }
  } catch { /* fall through */ }
  // 纯文本
  const lines = content.split('\n').filter(l => l.trim())
  const result = lines.map(l => {
    const idx = l.indexOf(':')
    return idx > 0 ? { label: l.substring(0, idx).trim(), value: l.substring(idx + 1).trim() } : null
  }).filter(Boolean)
  return result.length ? result : null
})
</script>

<style scoped>
.notification-logs { padding: 20px; background: #fff; border-radius: 8px; }
.filters { margin-bottom: 20px; padding: 20px; background: #f8f9fa; border-radius: 6px; }
.pagination { margin-top: 20px; display: flex; justify-content: flex-end; }
.content-box { width: 100%; }
.parsed-content { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #e4e7ed; }
.content-row { display: flex; padding: 10px 0; border-bottom: 1px solid #f0f2f5; }
.content-row:last-child { border-bottom: none; }
.label { font-weight: 600; color: #606266; min-width: 90px; margin-right: 12px; }
.value { color: #303133; flex: 1; word-break: break-word; }
.raw-content { white-space: pre-wrap; word-break: break-word; margin: 0; padding: 12px; background: #f5f7fa; border-radius: 6px; font-size: 13px; max-height: 300px; overflow-y: auto; }
</style>
