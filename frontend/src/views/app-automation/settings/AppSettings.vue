<template>
  <div class="app-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span><el-icon><Setting /></el-icon> APP 自动化配置</span>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        style="max-width: 600px"
      >
        <el-form-item label="ADB 路径" prop="adb_path">
          <el-input
            v-model="form.adb_path"
            placeholder="例如: adb 或 D:\Android\platform-tools\adb.exe"
            clearable
          >
            <template #prepend>
              <el-icon><FolderOpened /></el-icon>
            </template>
          </el-input>
          <div class="form-item-tip">
            <el-text size="small" type="info">
              Android Debug Bridge 工具路径。如果 ADB 在系统 PATH 中，填写 "adb" 即可
            </el-text>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">
            <el-icon><Check /></el-icon>
            保存配置
          </el-button>
          <el-button @click="handleReset">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <div class="config-info">
        <el-descriptions title="当前配置信息" :column="1" border>
          <el-descriptions-item label="ADB 路径">
            <el-tag>{{ currentConfig.adb_path || 'adb' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="更新时间">
            {{ formatTime(currentConfig.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatTime(currentConfig.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, FolderOpened, Check, RefreshLeft } from '@element-plus/icons-vue'
import { getAppConfig, updateAppConfig } from '@/api/app-automation'
import { formatDateTime } from '@/utils/app-automation-helpers'

const formRef = ref(null)
const saving = ref(false)

const form = reactive({
  adb_path: 'adb'
})

const currentConfig = reactive({
  adb_path: '',
  created_at: '',
  updated_at: ''
})

const rules = {
  adb_path: [
    { required: true, message: '请输入 ADB 路径', trigger: 'blur' }
  ]
}

// 加载配置
const loadConfig = async () => {
  try {
    const res = await getAppConfig()
    if (res.data.success && res.data.data) {
      Object.assign(form, res.data.data)
      Object.assign(currentConfig, res.data.data)
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  }
}

// 保存配置
const handleSave = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    saving.value = true

    const res = await updateAppConfig(form)
    if (res.data.success) {
      ElMessage.success('配置保存成功')
      await loadConfig()
    } else {
      ElMessage.error(res.data.message || '配置保存失败')
    }
  } catch (error) {
    if (error !== false) { // 不是表单验证错误
      console.error('保存配置失败:', error)
      ElMessage.error('保存配置失败')
    }
  } finally {
    saving.value = false
  }
}

// 重置表单
const handleReset = () => {
  Object.assign(form, currentConfig)
}

const formatTime = formatDateTime

onMounted(() => {
  loadConfig()
})
</script>

<style scoped lang="scss">
.app-settings {
  padding: 20px;

  .card-header {
    display: flex;
    align-items: center;
    font-weight: bold;
    
    span {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .form-item-tip {
    margin-top: 8px;
  }

  .config-info {
    margin-top: 20px;
  }
}
</style>
