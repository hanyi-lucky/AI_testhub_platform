<template>
  <div class="report-list">
    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ==================== 套件报告 ==================== -->
      <el-tab-pane label="套件报告" name="suite">
        <!-- 统计 -->
        <div class="stats-row">
          <el-card v-for="stat in suiteStatsCards" :key="stat.label" class="stat-card" shadow="hover">
            <div class="stat-content">
              <div class="stat-number" :style="{ color: stat.color }">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </el-card>
        </div>

        <!-- 筛选 -->
        <div class="filters">
          <el-row :gutter="20">
            <el-col :span="4">
              <el-select v-model="suiteProjectFilter" placeholder="全部项目" clearable filterable @change="loadSuiteReports">
                <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input v-model="suiteSearch" placeholder="搜索套件名称" clearable @clear="loadSuiteReports" @keyup.enter="loadSuiteReports">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </el-col>
            <el-col :span="5">
              <el-select v-model="suiteStatusFilter" placeholder="执行状态" clearable @change="loadSuiteReports">
                <el-option label="全部" value="" />
                <el-option label="已完成" value="completed" />
                <el-option label="执行异常" value="error" />
                <el-option label="执行中" value="running" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-button type="primary" @click="loadSuiteReports"><el-icon><Search /></el-icon>查询</el-button>
              <el-button @click="suiteSearch = ''; suiteStatusFilter = ''; suiteProjectFilter = null; loadSuiteReports()">重置</el-button>
            </el-col>
          </el-row>
        </div>

        <!-- 套件报告列表 -->
        <el-table :data="suiteReports" v-loading="suiteLoading" border stripe>
          <el-table-column prop="name" label="套件名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.description || '-' }}</template>
          </el-table-column>
          <el-table-column label="执行状态" min-width="90">
            <template #default="{ row }">
              <el-tag :type="getSuiteDisplayStatus(row).type" size="small">
                {{ getSuiteDisplayStatus(row).text }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="用例通过率" min-width="140">
            <template #default="{ row }">
              <el-progress
                v-if="row.test_case_count > 0"
                :percentage="getSuitePassRate(row)"
                :color="getPassRateColor(getSuitePassRate(row))"
                :stroke-width="16"
                :text-inside="true"
              />
              <span v-else style="color:#909399">无用例</span>
            </template>
          </el-table-column>
          <el-table-column label="用例统计" min-width="180">
            <template #default="{ row }">
              <div class="step-stats">
                <span style="color:#67c23a">通过 {{ row.passed_count || 0 }}</span>
                <el-divider direction="vertical" />
                <span style="color:#f56c6c">失败 {{ row.failed_count || 0 }}</span>
                <el-divider direction="vertical" />
                <span>总计 {{ row.test_case_count || 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="创建人" min-width="80">
            <template #default="{ row }">{{ row.created_by_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="最后执行" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.last_run_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="200">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="viewSuiteDetail(row)">详情</el-button>
              <el-button type="success" link size="small" @click="viewSuiteExecutions(row)">执行记录</el-button>
              <el-button type="success" link size="small" @click="viewSuiteAllureReport(row)">Allure报告</el-button>
              <el-button type="danger" link size="small" @click="deleteSuiteReport(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination">
          <el-pagination
            v-model:current-page="suitePagination.current"
            v-model:page-size="suitePagination.size"
            :total="suitePagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadSuiteReports"
            @current-change="loadSuiteReports"
          />
        </div>
      </el-tab-pane>

      <!-- ==================== 用例报告 ==================== -->
      <el-tab-pane label="用例报告" name="case">
        <!-- 统计 -->
        <div class="stats-row">
          <el-card v-for="stat in caseStatsCards" :key="stat.label" class="stat-card" shadow="hover">
            <div class="stat-content">
              <div class="stat-number" :style="{ color: stat.color }">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </el-card>
        </div>

        <!-- 筛选 -->
        <div class="filters">
          <el-row :gutter="20">
            <el-col :span="4">
              <el-select v-model="caseProjectFilter" placeholder="全部项目" clearable filterable @change="loadCaseReports">
                <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input v-model="caseSearch" placeholder="搜索用例名称、设备" clearable @clear="loadCaseReports" @keyup.enter="loadCaseReports">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </el-col>
            <el-col :span="4">
              <el-select v-model="caseStatusFilter" placeholder="执行状态" clearable @change="loadCaseReports">
                <el-option label="全部" value="" />
                <el-option label="已完成" value="completed" />
                <el-option label="执行异常" value="error" />
                <el-option label="已停止" value="stopped" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-button type="primary" @click="loadCaseReports"><el-icon><Search /></el-icon>查询</el-button>
              <el-button @click="caseSearch = ''; caseStatusFilter = ''; caseProjectFilter = null; loadCaseReports()">重置</el-button>
            </el-col>
          </el-row>
        </div>

        <!-- 用例报告列表 -->
        <el-table :data="caseReports" v-loading="caseLoading" border stripe>
          <el-table-column label="测试用例" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">{{ row.case_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="设备" min-width="100">
            <template #default="{ row }">{{ row.device_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="80">
            <template #default="{ row }">
              <el-tag :type="getDisplayStatus(row.status, row.result).type" size="small">
                {{ getDisplayStatus(row.status, row.result).text }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="步骤通过率" min-width="140">
            <template #default="{ row }">
              <el-progress
                :percentage="row.pass_rate || 0"
                :color="getPassRateColor(row.pass_rate)"
                :stroke-width="16"
                :text-inside="true"
              />
            </template>
          </el-table-column>
          <el-table-column label="步骤统计" min-width="180">
            <template #default="{ row }">
              <div class="step-stats">
                <span style="color:#67c23a">通过 {{ row.passed_steps || 0 }}</span>
                <el-divider direction="vertical" />
                <span style="color:#f56c6c">失败 {{ row.failed_steps || 0 }}</span>
                <el-divider direction="vertical" />
                <span>总计 {{ row.total_steps || 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="耗时" min-width="80">
            <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
          </el-table-column>
          <el-table-column label="执行人" min-width="80">
            <template #default="{ row }">{{ row.user_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="执行时间" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="150">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="viewCaseDetail(row)">详情</el-button>
              <el-button v-if="row.report_path" type="success" link size="small" @click="viewAllureReport(row)">Allure报告</el-button>
              <el-button type="danger" link size="small" @click="deleteCaseReport(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination">
          <el-pagination
            v-model:current-page="casePagination.current"
            v-model:page-size="casePagination.size"
            :total="casePagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadCaseReports"
            @current-change="loadCaseReports"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- ==================== 套件详情弹窗 ==================== -->
    <el-dialog v-model="suiteDetailVisible" title="套件报告详情" width="750px">
      <div v-if="selectedSuite">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="套件名称">{{ selectedSuite.name }}</el-descriptions-item>
          <el-descriptions-item label="执行状态">
            <el-tag :type="getSuiteDisplayStatus(selectedSuite).type">
              {{ getSuiteDisplayStatus(selectedSuite).text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ selectedSuite.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最后执行">{{ formatDateTime(selectedSuite.last_run_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 用例级统计 -->
        <div class="detail-section">
          <h4>用例统计</h4>
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="detail-stat success-bg">
                <div class="detail-stat-num">{{ selectedSuite.passed_count || 0 }}</div>
                <div class="detail-stat-label">通过用例</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="detail-stat danger-bg">
                <div class="detail-stat-num">{{ selectedSuite.failed_count || 0 }}</div>
                <div class="detail-stat-label">失败用例</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="detail-stat info-bg">
                <div class="detail-stat-num">{{ selectedSuite.test_case_count || 0 }}</div>
                <div class="detail-stat-label">总用例数</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <div class="detail-section">
          <h4>用例通过率</h4>
          <el-progress
            :percentage="getSuitePassRate(selectedSuite)"
            :color="getPassRateColor(getSuitePassRate(selectedSuite))"
            :stroke-width="20"
            :text-inside="true"
            style="margin-top:10px"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="suiteDetailVisible = false">关闭</el-button>
        <el-button type="primary" @click="suiteDetailVisible = false; viewSuiteExecutions(selectedSuite)">查看执行记录</el-button>
      </template>
    </el-dialog>

    <!-- ==================== 套件执行记录弹窗 ==================== -->
    <el-dialog v-model="suiteExecVisible" :title="`执行记录 - ${selectedSuite?.name || ''}`" width="900px">
      <el-table :data="suiteExecRecords" v-loading="suiteExecLoading" border stripe max-height="500">
        <el-table-column label="测试用例" min-width="180">
          <template #default="{ row }">{{ row.case_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getDisplayStatus(row.status, row.result).type" size="small">
              {{ getDisplayStatus(row.status, row.result).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="步骤统计" width="200">
          <template #default="{ row }">
            <div class="step-stats">
              <span style="color:#67c23a">通过 {{ row.passed_steps || 0 }}</span>
              <el-divider direction="vertical" />
              <span style="color:#f56c6c">失败 {{ row.failed_steps || 0 }}</span>
              <el-divider direction="vertical" />
              <span>总计 {{ row.total_steps || 0 }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
        </el-table-column>
        <el-table-column label="执行时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.report_path" type="success" link size="small" @click="viewAllureReport(row)">Allure报告</el-button>
            <el-button v-if="row.error_message" type="danger" link size="small" @click="viewCaseDetail(row)">错误</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="suiteExecVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ==================== 用例详情弹窗 ==================== -->
    <el-dialog v-model="caseDetailVisible" title="用例执行报告详情" width="700px">
      <div v-if="selectedCase">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="测试用例">{{ selectedCase.case_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行设备">{{ selectedCase.device_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行状态">
            <el-tag :type="getDisplayStatus(selectedCase.status, selectedCase.result).type">
              {{ getDisplayStatus(selectedCase.status, selectedCase.result).text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行人">{{ selectedCase.user_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDateTime(selectedCase.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatDateTime(selectedCase.finished_at) }}</el-descriptions-item>
          <el-descriptions-item label="执行耗时">{{ formatDuration(selectedCase.duration) }}</el-descriptions-item>
          <el-descriptions-item label="步骤通过率">
            <span :style="{ color: getPassRateColor(selectedCase.pass_rate), fontWeight: 'bold' }">
              {{ selectedCase.pass_rate || 0 }}%
            </span>
          </el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <h4>步骤统计</h4>
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="detail-stat success-bg">
                <div class="detail-stat-num">{{ selectedCase.passed_steps || 0 }}</div>
                <div class="detail-stat-label">通过步骤</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="detail-stat danger-bg">
                <div class="detail-stat-num">{{ selectedCase.failed_steps || 0 }}</div>
                <div class="detail-stat-label">失败步骤</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="detail-stat info-bg">
                <div class="detail-stat-num">{{ selectedCase.total_steps || 0 }}</div>
                <div class="detail-stat-label">总步骤数</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <div v-if="selectedCase.error_message" class="detail-section">
          <h4>错误信息</h4>
          <el-alert :title="selectedCase.error_message" type="error" show-icon :closable="false" />
        </div>

        <div v-if="selectedCase.report_path" class="detail-section" style="text-align:center">
          <el-button type="primary" @click="viewAllureReport(selectedCase)">
            <el-icon><DataAnalysis /></el-icon>
            查看完整 Allure 报告
          </el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="caseDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, DataAnalysis } from '@element-plus/icons-vue'
import {
  getExecutionList, deleteExecution,
  getTestSuiteList, getTestSuiteExecutions,
  getAppProjects,
} from '@/api/app-automation.js'
import { getExecutionStatusType, getExecutionStatusText, getDisplayStatus, formatDateTime } from '@/utils/app-automation-helpers.js'

// ==================== 公共 ====================
const activeTab = ref('suite')
const projectList = ref([])

function onTabChange(tab) {
  if (tab === 'suite' && suiteReports.value.length === 0) loadSuiteReports()
  if (tab === 'case' && caseReports.value.length === 0) loadCaseReports()
}

onMounted(() => {
  getAppProjects({ page_size: 100 }).then(res => { projectList.value = res.data.results || res.data || [] }).catch(() => {})
  loadSuiteReports()
})

// ==================== 套件报告 ====================
const suiteLoading = ref(false)
const suiteReports = ref([])
const suiteSearch = ref('')
const suiteStatusFilter = ref('')
const suiteProjectFilter = ref(null)
const suitePagination = reactive({ current: 1, size: 20, total: 0 })
const suiteDetailVisible = ref(false)
const suiteExecVisible = ref(false)
const suiteExecLoading = ref(false)
const suiteExecRecords = ref([])
const selectedSuite = ref(null)

const suiteStatsCards = computed(() => {
  const data = suiteReports.value
  const executed = data.filter(s => s.last_run_at)
  const success = executed.filter(s => s.execution_result === 'passed')
  const failed = executed.filter(s => s.execution_result === 'failed')
  const avgRate = executed.length > 0
    ? Math.round(executed.reduce((sum, s) => sum + getSuitePassRate(s), 0) / executed.length)
    : 0
  return [
    { label: '套件总数', value: suitePagination.total, color: '#409eff' },
    { label: '已执行', value: executed.length, color: '#67c23a' },
    { label: '最近失败', value: failed.length, color: '#f56c6c' },
    { label: '平均通过率', value: avgRate + '%', color: '#e6a23c' },
  ]
})

async function loadSuiteReports() {
  suiteLoading.value = true
  try {
    const params = { page: suitePagination.current, page_size: suitePagination.size }
    if (suiteProjectFilter.value) params.project = suiteProjectFilter.value
    if (suiteSearch.value) params.search = suiteSearch.value
    const res = await getTestSuiteList(params)
    let list = res.data.results || res.data || []
    // 状态筛选
    if (suiteStatusFilter.value) {
      list = list.filter(s => s.execution_status === suiteStatusFilter.value)
    }
    suiteReports.value = list
    suitePagination.total = res.data.count || list.length
  } catch { ElMessage.error('加载套件报告失败') }
  finally { suiteLoading.value = false }
}

function viewSuiteDetail(suite) {
  selectedSuite.value = suite
  suiteDetailVisible.value = true
}

async function viewSuiteExecutions(suite) {
  selectedSuite.value = suite
  suiteExecVisible.value = true
  suiteExecLoading.value = true
  try {
    const res = await getTestSuiteExecutions(suite.id)
    suiteExecRecords.value = res.data.data || res.data.results || res.data || []
  } catch { ElMessage.error('加载执行记录失败') }
  finally { suiteExecLoading.value = false }
}

async function viewSuiteAllureReport(suite) {
  // 获取该套件最近的执行记录，找到有 Allure 报告的
  try {
    const res = await getTestSuiteExecutions(suite.id)
    const records = res.data.data || res.data.results || res.data || []
    const withReport = records.find(r => r.report_path)
    if (withReport) {
      window.open(`/api/app-automation/executions/${withReport.id}/report/`, '_blank')
    } else {
      ElMessage.warning('该套件暂无 Allure 报告')
    }
  } catch { ElMessage.error('获取报告失败') }
}

async function deleteSuiteReport(suite) {
  try {
    await ElMessageBox.confirm(`确认删除套件「${suite.name}」？此操作不可恢复`, '删除确认', { type: 'warning' })
    const { deleteTestSuite } = await import('@/api/app-automation.js')
    await deleteTestSuite(suite.id)
    ElMessage.success('已删除')
    loadSuiteReports()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

function getSuitePassRate(suite) {
  const total = suite.test_case_count || 0
  if (total === 0) return 0
  return Math.round(((suite.passed_count || 0) / total) * 100)
}

function getSuiteDisplayStatus(row) {
  const status = row.execution_status
  const result = row.execution_result
  if (status === 'not_run') return { type: 'info', text: '未执行' }
  if (status === 'running') return { type: 'warning', text: '执行中' }
  if (status === 'error') return { type: 'danger', text: '执行异常' }
  if (result === 'passed') return { type: 'success', text: '通过' }
  if (result === 'failed') return { type: 'danger', text: '失败' }
  if (result === 'skipped') return { type: 'warning', text: '跳过' }
  // 向后兼容
  if (status === 'success') return { type: 'success', text: '通过' }
  if (status === 'failed') return { type: 'danger', text: '失败' }
  return { type: 'info', text: status }
}

// ==================== 用例报告 ====================
const caseLoading = ref(false)
const caseReports = ref([])
const caseSearch = ref('')
const caseStatusFilter = ref('')
const caseProjectFilter = ref(null)
const casePagination = reactive({ current: 1, size: 20, total: 0 })
const caseDetailVisible = ref(false)
const selectedCase = ref(null)

const caseStatsCards = computed(() => {
  const data = caseReports.value
  const success = data.filter(r => r.result === 'passed').length
  const failed = data.filter(r => r.result === 'failed').length
  const avgRate = data.length > 0
    ? Math.round(data.reduce((sum, r) => sum + (r.pass_rate || 0), 0) / data.length)
    : 0
  return [
    { label: '总报告数', value: casePagination.total, color: '#409eff' },
    { label: '本页通过', value: success, color: '#67c23a' },
    { label: '本页失败', value: failed, color: '#f56c6c' },
    { label: '本页平均通过率', value: avgRate + '%', color: '#e6a23c' },
  ]
})

async function loadCaseReports() {
  caseLoading.value = true
  try {
    const params = {
      page: casePagination.current,
      page_size: casePagination.size,
      ordering: '-created_at',
      'test_suite__isnull': true,  // 只查询单独执行的用例，排除套件执行记录
    }
    if (caseProjectFilter.value) params.project = caseProjectFilter.value
    if (caseStatusFilter.value) {
      params.status = caseStatusFilter.value
    } else {
      params.status__in = 'success,failed,stopped'
    }
    if (caseSearch.value) params.search = caseSearch.value

    const res = await getExecutionList(params)
    caseReports.value = res.data.results || []
    casePagination.total = res.data.count || 0
  } catch { ElMessage.error('加载用例报告失败') }
  finally { caseLoading.value = false }
}

function viewCaseDetail(row) {
  selectedCase.value = row
  caseDetailVisible.value = true
}

function viewAllureReport(row) {
  if (!row.report_path) return ElMessage.warning('该记录没有 Allure 报告')
  window.open(`/api/app-automation/executions/${row.id}/report/`, '_blank')
}

async function deleteCaseReport(row) {
  try {
    await ElMessageBox.confirm('确认删除该执行报告？', '删除确认', { type: 'warning' })
    await deleteExecution(row.id)
    ElMessage.success('已删除')
    loadCaseReports()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

// getDisplayStatus 已从 helpers 导入

function getPassRateColor(rate) {
  if (rate >= 80) return '#67c23a'
  if (rate >= 50) return '#e6a23c'
  return '#f56c6c'
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.floor(seconds)}秒`
  const min = Math.floor(seconds / 60)
  const sec = Math.floor(seconds % 60)
  return `${min}分${sec}秒`
}
</script>

<style scoped>
.report-list { padding: 20px; }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; }
.stat-card { flex: 1; }
.stat-content { text-align: center; }
.stat-number { font-size: 28px; font-weight: bold; line-height: 1.6; }
.stat-label { font-size: 13px; color: #909399; }
.filters { margin-bottom: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; }
.pagination { margin-top: 20px; display: flex; justify-content: flex-end; }
.step-stats { display: flex; align-items: center; font-size: 13px; }
.detail-section { margin-top: 24px; }
.detail-section h4 { margin-bottom: 12px; color: #303133; }
.detail-stat { text-align: center; padding: 16px; border-radius: 8px; }
.detail-stat-num { font-size: 24px; font-weight: bold; }
.detail-stat-label { font-size: 13px; color: #606266; margin-top: 4px; }
.success-bg { background: #f0f9eb; color: #67c23a; }
.danger-bg { background: #fef0f0; color: #f56c6c; }
.info-bg { background: #f4f4f5; color: #909399; }
</style>
