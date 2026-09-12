<template>
  <div class="suite-list">
    <!-- 页面标题 -->
    <div class="page-header">
      <h3>测试套件</h3>
      <div class="header-actions">
        <el-button type="primary" size="small" :icon="Plus" @click="showCreateDialog">
          新建套件
        </el-button>
        <el-button size="small" :icon="Refresh" :loading="loading" @click="loadSuites">
          刷新
        </el-button>
      </div>
    </div>

    <!-- 设备和应用选择 -->
    <el-card class="config-card">
      <el-form :model="runConfig" label-width="100px" size="small">
        <el-row :gutter="16">
          <el-col :span="5">
            <el-form-item label="所属项目">
              <el-select v-model="projectFilter" placeholder="全部项目" clearable filterable style="width:100%" @change="loadSuites">
                <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="选择设备" required>
              <el-select
                v-model="runConfig.deviceId"
                placeholder="请选择设备"
                filterable
                style="width: 100%"
                :loading="devicesLoading"
              >
                <el-option
                  v-for="device in availableDevices"
                  :key="device.id"
                  :label="`${device.name || device.device_id} (${device.device_id})`"
                  :value="device.device_id"
                  :disabled="device.status !== 'available' && device.status !== 'online'"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="选择应用">
              <el-select
                v-model="runConfig.packageName"
                placeholder="请选择应用（可选）"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="pkg in appPackages"
                  :key="pkg.id"
                  :label="`${pkg.name} (${pkg.package_name})`"
                  :value="pkg.package_name"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="搜索套件">
              <el-input
                v-model="searchQuery"
                placeholder="搜索套件名称"
                clearable
                @clear="loadSuites"
                @keyup.enter="loadSuites"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 套件列表 -->
    <el-table
      v-loading="loading"
      :data="suites"
      style="width: 100%; margin-top: 16px"
      empty-text="暂无测试套件"
    >
      <el-table-column prop="name" label="套件名称" min-width="180">
        <template #default="{ row }">
          <el-link type="primary" @click="showEditDialog(row)">{{ row.name }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="用例数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small">{{ row.test_case_count }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="执行状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="getSuiteDisplayStatus(row).type" size="small">
            {{ getSuiteDisplayStatus(row).text }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="通过/失败" width="110" align="center">
        <template #default="{ row }">
          <span v-if="row.execution_status !== 'not_run'" class="pass-fail">
            <span class="pass">{{ row.passed_count }}</span> /
            <span class="fail">{{ row.failed_count }}</span>
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="最后执行" width="170">
        <template #default="{ row }">
          {{ row.last_run_at ? formatDateTime(row.last_run_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="success" size="small" @click="runSuite(row)">
            执行
          </el-button>
          <el-button link type="primary" size="small" @click="showEditDialog(row)">
            编辑
          </el-button>
          <el-button link type="warning" size="small" @click="showSuiteExecutions(row)">
            历史
          </el-button>
          <el-button link type="danger" size="small" @click="deleteSuite(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑套件对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑测试套件' : '新建测试套件'"
      width="900px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="suiteForm" label-width="80px" size="default">
        <el-form-item label="套件名称" required>
          <el-input v-model="suiteForm.name" placeholder="请输入套件名称" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="suiteForm.project" placeholder="请选择项目" clearable filterable style="width:100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="suiteForm.description" type="textarea" :rows="2" placeholder="请输入套件描述" />
        </el-form-item>
      </el-form>

      <!-- 用例选择器（双栏） -->
      <div class="case-selector">
        <div class="selector-panel available-panel">
          <div class="panel-header">
            <span>可选用例</span>
            <el-input
              v-model="caseSearchQuery"
              placeholder="搜索用例"
              size="small"
              clearable
              style="width: 200px"
              @input="filterAvailableCases"
            />
          </div>
          <div class="panel-body">
            <div
              v-for="tc in filteredAvailableCases"
              :key="tc.id"
              class="case-item"
              :class="{ disabled: selectedCaseIds.has(tc.id) }"
              @click="addCase(tc)"
            >
              <span class="case-name">{{ tc.name }}</span>
              <span class="case-pkg">{{ tc.app_package_name || '' }}</span>
              <el-icon v-if="!selectedCaseIds.has(tc.id)" class="add-icon"><Plus /></el-icon>
              <el-icon v-else class="added-icon"><Check /></el-icon>
            </div>
            <el-empty v-if="filteredAvailableCases.length === 0" description="暂无可选用例" :image-size="60" />
          </div>
        </div>

        <div class="selector-panel selected-panel">
          <div class="panel-header">
            <span>已选用例 ({{ selectedCases.length }})</span>
            <el-button v-if="selectedCases.length" link type="danger" size="small" @click="clearAllCases">
              清空
            </el-button>
          </div>
          <div class="panel-body">
            <draggable
              v-model="selectedCases"
              item-key="id"
              handle=".drag-handle"
              animation="200"
            >
              <template #item="{ element, index }">
                <div class="case-item selected">
                  <el-icon class="drag-handle"><Rank /></el-icon>
                  <span class="case-order">{{ index + 1 }}</span>
                  <span class="case-name">{{ element.name }}</span>
                  <el-icon class="remove-icon" @click="removeCase(index)"><Close /></el-icon>
                </div>
              </template>
            </draggable>
            <el-empty v-if="selectedCases.length === 0" description="请从左侧添加用例" :image-size="60" />
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSuite">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 执行历史对话框 -->
    <el-dialog
      v-model="historyVisible"
      :title="`执行历史 - ${currentSuiteName}`"
      width="900px"
      destroy-on-close
    >
      <el-table :data="suiteExecutions" v-loading="historyLoading" empty-text="暂无执行记录">
        <el-table-column prop="case_name" label="测试用例" min-width="180" />
        <el-table-column prop="device_name" label="设备" width="150" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getDisplayStatus(row.status, row.result).type" size="small">
              {{ getDisplayStatus(row.status, row.result).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress || 0"
              :status="getProgressStatus(row)"
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">
            {{ row.started_at ? formatDateTime(row.started_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed' || row.status === 'error'"
              link type="primary" size="small"
              @click="viewReport(row)"
            >
              查看报告
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search, Check, Close, Rank } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import {
  getTestSuiteList,
  getTestSuiteDetail,
  createTestSuite,
  updateTestSuite,
  deleteTestSuite as apiDeleteSuite,
  addTestCasesToSuite,
  removeTestCaseFromSuite,
  updateSuiteTestCaseOrder,
  runTestSuite,
  getTestSuiteExecutions,
  getTestCaseList,
  getDeviceList,
  getPackageList,
  getAppProjects,
} from '@/api/app-automation'
import { getExecutionStatusType, getExecutionStatusText, getDisplayStatus, formatDateTime } from '@/utils/app-automation-helpers'

// ===== 响应式数据 =====
const loading = ref(false)
const devicesLoading = ref(false)
const saving = ref(false)
const historyLoading = ref(false)
const searchQuery = ref('')
const projectFilter = ref(null)
const projectList = ref([])

const suites = ref([])
const availableDevices = ref([])
const appPackages = ref([])
const allTestCases = ref([])

const runConfig = ref({
  deviceId: null,
  packageName: null
})

// 对话框
const dialogVisible = ref(false)
const historyVisible = ref(false)
const isEdit = ref(false)
const editingSuiteId = ref(null)
const currentSuiteName = ref('')

const suiteForm = ref({
  name: '',
  description: '',
  project: null
})

// 用例选择
const caseSearchQuery = ref('')
const selectedCases = ref([])
const suiteExecutions = ref([])

const selectedCaseIds = computed(() => new Set(selectedCases.value.map(c => c.id)))

const filteredAvailableCases = computed(() => {
  const query = caseSearchQuery.value.toLowerCase()
  if (!query) return allTestCases.value
  return allTestCases.value.filter(tc =>
    tc.name.toLowerCase().includes(query) ||
    (tc.app_package_name && tc.app_package_name.toLowerCase().includes(query))
  )
})

// ===== 加载数据 =====
const loadSuites = async () => {
  loading.value = true
  try {
    const params = { search: searchQuery.value }
    if (projectFilter.value) params.project = projectFilter.value
    const res = await getTestSuiteList(params)
    const data = res.data
    suites.value = data.results || data || []
  } catch (error) {
    console.error('加载套件列表失败:', error)
    suites.value = []
  } finally {
    loading.value = false
  }
}

const loadDevices = async () => {
  devicesLoading.value = true
  try {
    const res = await getDeviceList({ page_size: 100 })
    const data = res.data
    if (data.success !== undefined) {
      availableDevices.value = data.data?.results || data.data || []
    } else {
      availableDevices.value = data.results || data || []
    }
  } catch (error) {
    console.error('加载设备失败:', error)
    availableDevices.value = []
  } finally {
    devicesLoading.value = false
  }
}

const loadPackages = async () => {
  try {
    const res = await getPackageList({ page_size: 200 })
    const data = res.data
    if (data.success !== undefined) {
      appPackages.value = data.data?.results || data.data || []
    } else {
      appPackages.value = data.results || data || []
    }
  } catch (error) {
    appPackages.value = []
  }
}

const loadAllTestCases = async () => {
  try {
    const res = await getTestCaseList({ page_size: 500 })
    const data = res.data
    let cases = []
    if (data.success !== undefined) {
      cases = data.data?.results || data.data || []
    } else {
      cases = data.results || data || []
    }
    allTestCases.value = cases.map(tc => ({
      id: tc.id,
      name: tc.name,
      description: tc.description || '',
      app_package_name: tc.app_package_name || ''
    }))
  } catch (error) {
    allTestCases.value = []
  }
}

// ===== 套件操作 =====
const showCreateDialog = () => {
  isEdit.value = false
  editingSuiteId.value = null
  suiteForm.value = { name: '', description: '', project: null }
  selectedCases.value = []
  caseSearchQuery.value = ''
  dialogVisible.value = true
  loadAllTestCases()
}

const showEditDialog = async (suite) => {
  isEdit.value = true
  editingSuiteId.value = suite.id
  suiteForm.value = { name: suite.name, description: suite.description || '', project: suite.project || null }
  caseSearchQuery.value = ''
  dialogVisible.value = true

  await loadAllTestCases()

  // 加载套件中已有的用例
  try {
    const res = await getTestSuiteDetail(suite.id)
    const data = res.data
    const suiteCases = data.suite_cases || []
    selectedCases.value = suiteCases
      .sort((a, b) => a.order - b.order)
      .map(sc => ({
        id: sc.test_case.id,
        name: sc.test_case.name,
        description: sc.test_case.description || '',
        app_package_name: sc.test_case.app_package_name || ''
      }))
  } catch (error) {
    console.error('加载套件用例失败:', error)
    selectedCases.value = []
  }
}

const saveSuite = async () => {
  if (!suiteForm.value.name.trim()) {
    ElMessage.warning('请输入套件名称')
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      // 更新套件基本信息
      await updateTestSuite(editingSuiteId.value, {
        name: suiteForm.value.name,
        description: suiteForm.value.description,
        project: suiteForm.value.project || null
      })

      // 同步用例：获取当前套件中的用例
      const detailRes = await getTestSuiteDetail(editingSuiteId.value)
      const currentCases = (detailRes.data.suite_cases || []).map(sc => sc.test_case.id)
      const newCaseIds = selectedCases.value.map(c => c.id)

      // 移除不在新列表中的
      for (const cid of currentCases) {
        if (!newCaseIds.includes(cid)) {
          await removeTestCaseFromSuite(editingSuiteId.value, { test_case_id: cid })
        }
      }

      // 添加新的
      const toAdd = newCaseIds.filter(id => !currentCases.includes(id))
      if (toAdd.length) {
        await addTestCasesToSuite(editingSuiteId.value, { test_case_ids: toAdd })
      }

      // 更新顺序
      const orderData = selectedCases.value.map((c, idx) => ({
        test_case_id: c.id,
        order: idx
      }))
      await updateSuiteTestCaseOrder(editingSuiteId.value, { test_case_orders: orderData })

      ElMessage.success('套件更新成功')
    } else {
      // 创建套件
      await createTestSuite({
        name: suiteForm.value.name,
        description: suiteForm.value.description,
        project: suiteForm.value.project || null,
        test_case_ids: selectedCases.value.map(c => c.id)
      })
      ElMessage.success('套件创建成功')
    }

    dialogVisible.value = false
    loadSuites()
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.message || error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

const deleteSuite = async (suite) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除测试套件 "${suite.name}" 吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await apiDeleteSuite(suite.id)
    ElMessage.success('删除成功')
    loadSuites()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.message || '未知错误'))
    }
  }
}

// ===== 用例选择操作 =====
const addCase = (tc) => {
  if (selectedCaseIds.value.has(tc.id)) return
  selectedCases.value.push({ ...tc })
}

const removeCase = (index) => {
  selectedCases.value.splice(index, 1)
}

const clearAllCases = () => {
  selectedCases.value = []
}

const filterAvailableCases = () => {
  // computed 自动处理
}

// ===== 执行套件 =====
const runSuite = async (suite) => {
  if (!runConfig.value.deviceId) {
    ElMessage.warning('请先选择设备')
    return
  }

  if (suite.test_case_count === 0) {
    ElMessage.warning('该套件未包含任何测试用例')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要执行测试套件 "${suite.name}" 吗？\n共 ${suite.test_case_count} 个用例`,
      '确认执行',
      { confirmButtonText: '执行', cancelButtonText: '取消', type: 'info' }
    )

    const params = { device_id: runConfig.value.deviceId }
    if (runConfig.value.packageName) {
      params.package_name = runConfig.value.packageName
    }

    const res = await runTestSuite(suite.id, params)
    const data = res.data

    if (data.success) {
      ElMessage.success(data.message || '套件已提交执行')
      // 延迟刷新
      setTimeout(() => loadSuites(), 2000)
    } else {
      ElMessage.error(data.message || '执行失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('执行失败: ' + (error.response?.data?.message || error.message || '未知错误'))
    }
  }
}

// ===== 执行历史 =====
const showSuiteExecutions = async (suite) => {
  currentSuiteName.value = suite.name
  historyVisible.value = true
  historyLoading.value = true

  try {
    const res = await getTestSuiteExecutions(suite.id)
    suiteExecutions.value = res.data.data || res.data || []
  } catch (error) {
    suiteExecutions.value = []
  } finally {
    historyLoading.value = false
  }
}

const viewReport = (execution) => {
  if (!execution.report_path) {
    ElMessage.info('报告路径不存在')
    return
  }
  window.open(`/api/app-automation/executions/${execution.id}/report/`, '_blank')
}

// ===== 工具方法 =====
const getSuiteDisplayStatus = (row) => {
  const status = row.execution_status
  const result = row.execution_result
  if (status === 'not_run') return { type: 'info', text: '未执行' }
  if (status === 'running') return { type: 'warning', text: '执行中' }
  if (status === 'error') return { type: 'danger', text: '执行异常' }
  // completed -> 显示测试结果
  if (result === 'passed') return { type: 'success', text: '通过' }
  if (result === 'failed') return { type: 'danger', text: '失败' }
  if (result === 'skipped') return { type: 'warning', text: '跳过' }
  // 向后兼容旧值
  if (status === 'success') return { type: 'success', text: '通过' }
  if (status === 'failed') return { type: 'danger', text: '失败' }
  return { type: 'info', text: status }
}

const getProgressStatus = (row) => {
  if (row.status === 'completed') {
    return row.result === 'failed' ? 'exception' : 'success'
  }
  if (row.status === 'error') return 'exception'
  return undefined
}

// ===== 初始化 =====
onMounted(() => {
  getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] }).catch(() => {})
  loadSuites()
  loadDevices()
  loadPackages()
})
</script>

<style scoped lang="scss">
.suite-list {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  background: white;
  padding: 16px 20px;
  border-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #303133;
  }

  .header-actions {
    display: flex;
    gap: 12px;
  }
}

.config-card {
  margin-bottom: 16px;

  :deep(.el-card__body) {
    padding: 20px;
  }

  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.pass-fail {
  .pass { color: #67c23a; font-weight: 600; }
  .fail { color: #f56c6c; font-weight: 600; }
}

/* 用例选择器 */
.case-selector {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  height: 400px;
}

.selector-panel {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: #f5f7fa;
    border-bottom: 1px solid #e4e7ed;
    font-weight: 600;
    font-size: 14px;
    color: #303133;
  }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
}

.case-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 4px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;

  &:hover {
    background: #ecf5ff;
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: #f5f7fa;
  }

  &.selected {
    background: #f0f9eb;
    cursor: grab;

    &:hover {
      background: #e1f3d8;
    }
  }

  .case-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .case-pkg {
    color: #909399;
    font-size: 12px;
    margin-left: 8px;
    flex-shrink: 0;
  }

  .case-order {
    color: #909399;
    font-size: 12px;
    margin: 0 8px;
    min-width: 20px;
    text-align: center;
  }

  .add-icon {
    color: #409eff;
    flex-shrink: 0;
  }

  .added-icon {
    color: #67c23a;
    flex-shrink: 0;
  }

  .drag-handle {
    cursor: grab;
    color: #c0c4cc;
    margin-right: 4px;
    flex-shrink: 0;
  }

  .remove-icon {
    color: #f56c6c;
    cursor: pointer;
    flex-shrink: 0;

    &:hover {
      color: #dd2020;
    }
  }
}

// 表格样式
:deep(.el-table) {
  .el-table__header th {
    background-color: #fafafa;
    color: #606266;
    font-weight: 600;
  }
}
</style>
