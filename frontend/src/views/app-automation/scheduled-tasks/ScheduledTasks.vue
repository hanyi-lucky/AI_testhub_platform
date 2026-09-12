<template>
  <div class="scheduled-tasks">
    <div class="header">
      <h3>APP定时任务</h3>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
    </div>

    <!-- 筛选 -->
    <div class="filters">
      <el-row :gutter="20">
        <el-col :span="5">
          <el-select v-model="filters.project" placeholder="全部项目" clearable filterable>
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.task_type" placeholder="任务类型" clearable>
            <el-option label="测试套件执行" value="TEST_SUITE" />
            <el-option label="测试用例执行" value="TEST_CASE" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.trigger_type" placeholder="触发器类型" clearable>
            <el-option label="Cron表达式" value="CRON" />
            <el-option label="固定间隔" value="INTERVAL" />
            <el-option label="单次执行" value="ONCE" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.status" placeholder="状态" clearable>
            <el-option label="激活" value="ACTIVE" />
            <el-option label="暂停" value="PAUSED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="失败" value="FAILED" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="primary" @click="loadTasks">查询</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 列表 -->
    <el-table :data="tasks" v-loading="loading" border>
      <el-table-column prop="name" label="任务名称" min-width="180" />
      <el-table-column prop="task_type" label="任务类型" width="120">
        <template #default="{ row }">
          <el-tag :type="row.task_type === 'TEST_SUITE' ? 'success' : 'primary'" size="small">
            {{ row.task_type_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trigger_type" label="触发器" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ row.trigger_type_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="通知" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.notification_type" :type="row.notification_type === 'webhook' ? 'primary' : row.notification_type === 'both' ? 'warning' : ''" size="small">
            {{ row.notification_type_display }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'PAUSED' ? 'warning' : 'info'" size="small">
            {{ row.status_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="设备" width="130">
        <template #default="{ row }">
          {{ row.device_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="下次执行" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.next_run_time) }}
        </template>
      </el-table-column>
      <el-table-column label="上次执行" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.last_run_time) }}
        </template>
      </el-table-column>
      <el-table-column label="执行统计" width="140">
        <template #default="{ row }">
          <span>总 {{ row.total_runs }}  </span>
          <span style="color:#67c23a">成功 {{ row.successful_runs }}  </span>
          <span style="color:#f56c6c">失败 {{ row.failed_runs }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="runNow(row)" :loading="row._running">执行</el-button>
          <el-dropdown @command="cmd => handleAction(cmd, row)">
            <el-button size="small">更多<el-icon><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="pause" v-if="row.status === 'ACTIVE'">暂停</el-dropdown-item>
                <el-dropdown-item command="resume" v-if="row.status === 'PAUSED'">恢复</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.current"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadTasks"
        @current-change="loadTasks"
      />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editingTask ? '编辑定时任务' : '新建定时任务'" width="720px" :close-on-click-modal="false" @close="resetForm">
      <el-form :model="form" label-width="110px">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="form.project" placeholder="请选择项目" clearable filterable style="width:100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>

        <el-form-item label="任务类型" required>
          <el-radio-group v-model="form.task_type">
            <el-radio value="TEST_SUITE">测试套件</el-radio>
            <el-radio value="TEST_CASE">测试用例</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'TEST_SUITE'" label="测试套件" required>
          <el-select v-model="form.test_suite" placeholder="选择套件" filterable>
            <el-option v-for="s in suites" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'TEST_CASE'" label="测试用例" required>
          <el-select v-model="form.test_case" placeholder="选择用例" filterable>
            <el-option v-for="tc in testCases" :key="tc.id" :label="tc.name" :value="tc.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="执行设备" required>
          <el-select v-model="form.device" placeholder="选择设备" filterable>
            <el-option v-for="d in devices" :key="d.id" :label="d.name || d.device_id" :value="d.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="应用包">
          <el-select v-model="form.app_package" placeholder="选择应用包" filterable clearable>
            <el-option v-for="p in packages" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="触发器类型" required>
          <el-radio-group v-model="form.trigger_type">
            <el-radio value="CRON">Cron表达式</el-radio>
            <el-radio value="INTERVAL">固定间隔</el-radio>
            <el-radio value="ONCE">单次执行</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'CRON'" label="Cron表达式" required>
          <el-input v-model="form.cron_expression" placeholder="如: 0 0 * * *" />
          <div class="cron-help">
            <el-tooltip raw-content placement="top">
              <template #content>
                <div style="line-height: 1.6; text-align: left;">
                  <div>Cron表达式格式: 分 时 日 月 周</div>
                  <div>分: 0-59</div>
                  <div>时: 0-23</div>
                  <div>日: 1-31</div>
                  <div>月: 1-12 或 JAN-DEC</div>
                  <div>周: 0-6 或 SUN-SAT (0=周日)</div>
                  <div style="margin-top: 8px;">常用示例:</div>
                  <div>每天0点: 0 0 * * *</div>
                  <div>每小时: 0 * * * *</div>
                  <div>每周一9点: 0 9 * * 1</div>
                  <div>每月1号0点: 0 0 1 * *</div>
                </div>
              </template>
              <span style="cursor: pointer; color: #409EFF;">Cron帮助</span>
            </el-tooltip>
          </div>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'INTERVAL'" label="间隔时间" required>
          <el-input-number v-model="form.interval_seconds" :min="60" :step="60" />
          <span class="unit">秒</span>
        </el-form-item>

        <el-form-item v-if="form.trigger_type === 'ONCE'" label="执行时间" required>
          <el-date-picker v-model="form.execute_at" type="datetime" placeholder="选择执行时间" />
        </el-form-item>

        <el-form-item label="通知设置">
          <el-checkbox v-model="form.notify_on_success">成功时通知</el-checkbox>
          <el-checkbox v-model="form.notify_on_failure">失败时通知</el-checkbox>
        </el-form-item>

        <el-form-item v-if="form.notify_on_success || form.notify_on_failure" label="通知类型">
          <el-select v-model="form.notification_type" placeholder="选择通知类型">
            <el-option label="邮箱通知" value="email" />
            <el-option label="Webhook机器人" value="webhook" />
            <el-option label="两者都发送" value="both" />
          </el-select>
        </el-form-item>

        <el-form-item
          v-if="(form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both')"
          label="通知邮箱"
        >
          <el-select v-model="form.notify_emails" multiple filterable allow-create placeholder="输入或选择邮箱">
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingTask ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import {
  getAppScheduledTasks,
  createAppScheduledTask,
  updateAppScheduledTask,
  deleteAppScheduledTask,
  pauseAppScheduledTask,
  resumeAppScheduledTask,
  runAppScheduledTask,
  getTestSuiteList,
  getTestCaseList,
  getDeviceList,
  getPackageList,
  getAppProjects,
} from '@/api/app-automation.js'

const projectList = ref([])
const tasks = ref([])
const suites = ref([])
const testCases = ref([])
const devices = ref([])
const packages = ref([])
const loading = ref(false)
const submitting = ref(false)
const showDialog = ref(false)
const editingTask = ref(null)

const filters = reactive({ project: null, task_type: '', trigger_type: '', status: '' })
const pagination = reactive({ current: 1, size: 10, total: 0 })

const defaultForm = {
  name: '', description: '', project: null, task_type: 'TEST_SUITE', trigger_type: 'CRON',
  cron_expression: '0 0 * * *', interval_seconds: 3600, execute_at: '',
  device: '', app_package: '', test_suite: '', test_case: '',
  notify_on_success: false, notify_on_failure: false,
  notification_type: '', notify_emails: [],
}
const form = reactive({ ...defaultForm })

onMounted(() => {
  getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] }).catch(() => {})
  loadTasks()
  loadOptions()
})

const loadTasks = async () => {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.size }
    if (filters.project) params.project = filters.project
    if (filters.task_type) params.task_type = filters.task_type
    if (filters.trigger_type) params.trigger_type = filters.trigger_type
    if (filters.status) params.status = filters.status
    const res = await getAppScheduledTasks(params)
    tasks.value = (res.data.results || []).map(t => ({ ...t, _running: false }))
    pagination.total = res.data.count || 0
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

const loadOptions = async () => {
  try {
    const [s, tc, d, p] = await Promise.all([
      getTestSuiteList({ page_size: 200 }),
      getTestCaseList({ page_size: 500 }),
      getDeviceList({ page_size: 100 }),
      getPackageList({ page_size: 100 }),
    ])
    suites.value = s.data.results || s.data || []
    testCases.value = tc.data.results || tc.data || []
    devices.value = d.data.results || d.data || []
    packages.value = p.data.results || p.data || []
  } catch (e) { console.error('加载选项失败', e) }
}

const handleCreate = () => {
  editingTask.value = null
  resetForm()
  showDialog.value = true
}

const resetForm = () => Object.assign(form, { ...defaultForm, notify_emails: [] })
const resetFilters = () => { Object.assign(filters, { project: null, task_type: '', trigger_type: '', status: '' }); loadTasks() }

const submitForm = async () => {
  if (!form.name) return ElMessage.warning('请输入任务名称')
  if (!form.device) return ElMessage.warning('请选择设备')

  submitting.value = true
  try {
    const data = { ...form }
    // 清理多余字段
    if (data.task_type === 'TEST_SUITE') delete data.test_case
    else delete data.test_suite
    if (data.trigger_type !== 'CRON') delete data.cron_expression
    if (data.trigger_type !== 'INTERVAL') delete data.interval_seconds
    if (data.trigger_type !== 'ONCE') delete data.execute_at
    if (!data.notify_on_success && !data.notify_on_failure) {
      delete data.notification_type
      delete data.notify_emails
    }
    if (!data.app_package) delete data.app_package

    if (editingTask.value) {
      await updateAppScheduledTask(editingTask.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createAppScheduledTask(data)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    loadTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.message || '操作失败')
  } finally { submitting.value = false }
}

const runNow = async (task) => {
  task._running = true
  try {
    await runAppScheduledTask(task.id)
    ElMessage.success('任务已开始执行')
    setTimeout(loadTasks, 2000)
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '执行失败')
  } finally { task._running = false }
}

const handleAction = (cmd, task) => {
  switch (cmd) {
    case 'edit': editTask(task); break
    case 'pause': pauseTask(task); break
    case 'resume': resumeTask(task); break
    case 'delete': deleteTask(task); break
  }
}

const editTask = (task) => {
  editingTask.value = task
  Object.assign(form, {
    name: task.name, description: task.description || '',
    task_type: task.task_type, trigger_type: task.trigger_type,
    cron_expression: task.cron_expression || '0 0 * * *',
    interval_seconds: task.interval_seconds || 3600,
    execute_at: task.execute_at || '',
    device: task.device || '', app_package: task.app_package || '',
    test_suite: task.test_suite || '', test_case: task.test_case || '',
    notify_on_success: task.notify_on_success || false,
    notify_on_failure: task.notify_on_failure || false,
    notification_type: task.notification_type || '',
    notify_emails: task.notify_emails || [],
  })
  showDialog.value = true
}

const pauseTask = async (task) => {
  try { await pauseAppScheduledTask(task.id); ElMessage.success('已暂停'); loadTasks() }
  catch { ElMessage.error('暂停失败') }
}
const resumeTask = async (task) => {
  try { await resumeAppScheduledTask(task.id); ElMessage.success('已恢复'); loadTasks() }
  catch { ElMessage.error('恢复失败') }
}
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm(`确认删除任务「${task.name}」？`, '删除确认', { type: 'warning' })
    await deleteAppScheduledTask(task.id)
    ElMessage.success('已删除')
    loadTasks()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

const formatDateTime = (s) => {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).replace(/\//g, '-')
}
</script>

<style scoped>
.scheduled-tasks { padding: 20px; display: flex; flex-direction: column; height: 100%; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.filters { margin-bottom: 20px; background: #f8f9fa; padding: 20px; border-radius: 8px; }
.pagination { margin-top: 20px; display: flex; justify-content: flex-end; }
.cron-help { margin-top: 8px; font-size: 12px; }
.unit { margin-left: 8px; color: #606266; }
</style>
