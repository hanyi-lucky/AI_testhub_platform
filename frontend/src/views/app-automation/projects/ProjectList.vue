<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">APP项目管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>新建项目
      </el-button>
    </div>

    <div class="card-container">
      <!-- 筛选 -->
      <div class="filter-bar">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-input v-model="searchText" placeholder="搜索项目名称" clearable @clear="loadProjects" @keyup.enter="loadProjects">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select v-model="statusFilter" placeholder="项目状态" clearable @change="loadProjects">
              <el-option label="未开始" value="NOT_STARTED" />
              <el-option label="进行中" value="IN_PROGRESS" />
              <el-option label="已结束" value="COMPLETED" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="loadProjects"><el-icon><Search /></el-icon>查询</el-button>
            <el-button @click="searchText = ''; statusFilter = ''; loadProjects()">重置</el-button>
          </el-col>
        </el-row>
      </div>

      <!-- 项目列表 -->
      <el-table :data="projects" v-loading="loading" border stripe>
        <el-table-column prop="name" label="项目名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用例数" min-width="70" align="center">
          <template #default="{ row }">{{ row.test_case_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="套件数" min-width="70" align="center">
          <template #default="{ row }">{{ row.test_suite_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="负责人" min-width="80">
          <template #default="{ row }">{{ row.owner_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="成员数" min-width="70" align="center">
          <template #default="{ row }">{{ row.member_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="开始日期" min-width="110">
          <template #default="{ row }">{{ row.start_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="结束日期" min-width="110">
          <template #default="{ row }">{{ row.end_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="150">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
            <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadProjects"
          @current-change="loadProjects"
        />
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目' : '新建项目'" width="520px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="80px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入项目描述" />
        </el-form-item>
        <el-form-item label="项目状态" prop="status">
          <el-select v-model="form.status" placeholder="请选择状态" style="width:100%">
            <el-option label="未开始" value="NOT_STARTED" />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="已结束" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="form.start_date" type="date" placeholder="选择开始日期" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.end_date" type="date" placeholder="选择结束日期" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="项目详情" width="600px">
      <div v-if="selectedProject">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目名称">{{ selectedProject.name }}</el-descriptions-item>
          <el-descriptions-item label="项目状态">
            <el-tag :type="getStatusType(selectedProject.status)">{{ getStatusText(selectedProject.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ selectedProject.owner_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="成员数">{{ selectedProject.member_count || 0 }} 人</el-descriptions-item>
          <el-descriptions-item label="测试用例">{{ selectedProject.test_case_count || 0 }} 个</el-descriptions-item>
          <el-descriptions-item label="测试套件">{{ selectedProject.test_suite_count || 0 }} 个</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ selectedProject.start_date || '未设置' }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ selectedProject.end_date || '未设置' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ formatDateTime(selectedProject.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="项目描述" :span="2">{{ selectedProject.description || '无描述' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getAppProjects, createAppProject, updateAppProject, deleteAppProject } from '@/api/app-automation.js'

const loading = ref(false)
const submitting = ref(false)
const projects = ref([])
const searchText = ref('')
const statusFilter = ref('')
const pagination = reactive({ current: 1, size: 20, total: 0 })

// 对话框
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const form = reactive({
  name: '',
  description: '',
  status: 'IN_PROGRESS',
  start_date: null,
  end_date: null,
})
const formRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 200, message: '长度在 2 到 200 个字符', trigger: 'blur' },
  ],
}

// 详情
const detailVisible = ref(false)
const selectedProject = ref(null)

onMounted(loadProjects)

async function loadProjects() {
  loading.value = true
  try {
    const params = { page: pagination.current, page_size: pagination.size }
    if (searchText.value) params.search = searchText.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getAppProjects(params)
    projects.value = res.data.results || res.data || []
    pagination.total = res.data.count || projects.value.length
  } catch { ElMessage.error('加载项目列表失败') }
  finally { loading.value = false }
}

function openCreateDialog() {
  isEdit.value = false
  editId.value = null
  Object.assign(form, { name: '', description: '', status: 'IN_PROGRESS', start_date: null, end_date: null })
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    status: row.status,
    start_date: row.start_date || null,
    end_date: row.end_date || null,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateAppProject(editId.value, { ...form })
      ElMessage.success('项目更新成功')
    } else {
      await createAppProject({ ...form })
      ElMessage.success('项目创建成功')
    }
    dialogVisible.value = false
    loadProjects()
  } catch (e) {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  } finally { submitting.value = false }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除项目「${row.name}」？此操作不可恢复`, '删除确认', { type: 'warning' })
    await deleteAppProject(row.id)
    ElMessage.success('已删除')
    loadProjects()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

function viewDetail(row) {
  selectedProject.value = row
  detailVisible.value = true
}

function getStatusType(status) {
  const map = { 'NOT_STARTED': 'warning', 'IN_PROGRESS': 'primary', 'COMPLETED': 'success' }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = { 'NOT_STARTED': '未开始', 'IN_PROGRESS': '进行中', 'COMPLETED': '已结束' }
  return map[status] || status
}

function formatDateTime(dt) {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; font-size: 20px; }
.card-container { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.filter-bar { margin-bottom: 20px; }
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>
