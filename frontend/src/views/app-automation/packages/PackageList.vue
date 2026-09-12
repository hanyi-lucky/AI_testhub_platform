<template>
  <div class="app-package-list">
    <div class="page-header">
      <h3>包名管理</h3>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadPackages">
          刷新
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          新增包名
        </el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="packages"
      style="width: 100%; margin-top: 16px"
      empty-text="暂无应用包名"
    >
      <el-table-column prop="name" label="应用名称" min-width="180" />
      <el-table-column prop="package_name" label="应用包名" min-width="220" />
      <el-table-column prop="created_by_name" label="创建人" width="120">
        <template #default="{ row }">
          {{ row.created_by_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link size="small" type="primary" @click="openEditDialog(row)">
            编辑
          </el-button>
          <el-button link size="small" type="danger" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-show="total > 0"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      style="margin-top: 16px; text-align: right"
      @size-change="loadPackages"
      @current-change="loadPackages"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="应用名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：Android设置" />
        </el-form-item>
        <el-form-item label="应用包名" prop="package_name">
          <el-input v-model="form.package_name" placeholder="例如：com.android.settings" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  getPackageList,
  createPackage,
  updatePackage,
  deletePackage
} from '@/api/app-automation'
import { formatDateTime } from '@/utils/app-automation-helpers'

const loading = ref(false)
const saving = ref(false)
const packages = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const dialogVisible = ref(false)
const dialogTitle = ref('新增包名')
const isEditing = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  name: '',
  package_name: ''
})

const rules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
  package_name: [{ required: true, message: '请输入应用包名', trigger: 'blur' }]
}

const loadPackages = async () => {
  loading.value = true
  try {
    const res = await getPackageList({
      page: currentPage.value,
      page_size: pageSize.value
    })
    const data = res.data
    const payload = data.success !== undefined ? data.data : data
    packages.value = payload?.results || payload || []
    total.value = payload?.count || packages.value.length || 0
  } catch (error) {
    console.error('加载应用包名失败:', error)
    packages.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.package_name = ''
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  isEditing.value = false
  dialogTitle.value = '新增包名'
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEditing.value = true
  dialogTitle.value = '编辑包名'
  form.id = row.id
  form.name = row.name
  form.package_name = row.package_name
  dialogVisible.value = true
}

const submitForm = () => {
  formRef.value?.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (isEditing.value && form.id) {
        await updatePackage(form.id, {
          name: form.name,
          package_name: form.package_name
        })
        ElMessage.success('更新成功')
      } else {
        await createPackage({
          name: form.name,
          package_name: form.package_name
        })
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadPackages()
    } catch (error) {
      console.error('保存应用包名失败:', error)
      ElMessage.error(error?.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确认删除应用包名「${row.name}」吗？`,
    '删除确认',
    { type: 'warning' }
  ).then(async () => {
    try {
      await deletePackage(row.id)
      ElMessage.success('删除成功')
      loadPackages()
    } catch (error) {
      console.error('删除应用包名失败:', error)
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  }).catch(() => {})
}

// formatDateTime 已从 app-automation-helpers 导入

onMounted(() => {
  loadPackages()
})
</script>

<style scoped lang="scss">
.app-package-list {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  gap: 10px;
}
</style>
