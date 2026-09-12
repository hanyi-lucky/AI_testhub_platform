<template>
  <div class="device-management">
    <!-- 页面标题和操作按钮 -->
    <div class="device-header">
      <h3>设备管理</h3>
      <div class="device-actions">
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="refreshing"
          @click="refreshDevices"
        >
          刷新设备
        </el-button>
        <el-button
          type="success"
          :icon="Plus"
          @click="showAddRemoteDialog"
        >
          添加远程设备
        </el-button>
      </div>
    </div>

    <!-- 设备列表 -->
    <el-table
      v-loading="loading"
      :data="devices"
      style="width: 100%; margin-top: 20px"
      :empty-text="emptyText"
    >
      <el-table-column prop="name" label="设备名称" min-width="150">
        <template #default="{ row }">
          <span>{{ row.name || row.device_id }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="device_id" label="设备序列号" min-width="180" />

      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="locked_by" label="锁定用户" width="120">
        <template #default="{ row }">
          <span v-if="row.locked_by_name">
            {{ row.locked_by_name }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="locked_at" label="锁定时间" width="180">
        <template #default="{ row }">
          <span v-if="row.locked_at">
            {{ formatDate(row.locked_at) }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="android_version" label="Android版本" width="120" />

      <el-table-column prop="connection_type" label="连接类型" width="120">
        <template #default="{ row }">
          <el-tag
            :type="getConnectionType(row.connection_type) === 'local' ? 'primary' : 'warning'"
            size="small"
          >
            {{ getConnectionTypeName(row.connection_type) }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="ip_address" label="IP地址" width="150">
        <template #default="{ row }">
          <span v-if="row.ip_address">
            {{ row.ip_address }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="usage_count" label="使用次数" width="100" />

      <el-table-column prop="updated_at" label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>

      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'available' || row.status === 'online'"
            link
            size="small"
            type="primary"
            @click="lockDevice(row)"
          >
            锁定
          </el-button>
          <el-button
            v-if="row.status === 'locked'"
            link
            size="small"
            type="success"
            @click="unlockDevice(row)"
          >
            解锁
          </el-button>
          <el-button
            v-if="isRemoteDevice(row.connection_type) && row.status === 'offline'"
            link
            size="small"
            type="warning"
            :loading="reconnectingDevices[row.id]"
            @click="reconnectDevice(row)"
          >
            重连
          </el-button>
          <el-button
            link
            size="small"
            @click="viewDeviceInfo(row)"
          >
            详情
          </el-button>
          <el-button
            v-if="isRemoteDevice(row.connection_type) && (row.status === 'online' || row.status === 'available')"
            link
            size="small"
            type="warning"
            @click="disconnectDevice(row)"
          >
            断开
          </el-button>
          <el-button
            link
            size="small"
            type="danger"
            @click="handleDeleteDevice(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加远程设备对话框 -->
    <el-dialog
      v-model="addRemoteDialogVisible"
      title="添加远程设备"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="remoteDeviceFormRef"
        :model="remoteDeviceForm"
        :rules="remoteDeviceRules"
        label-width="100px"
      >
        <el-form-item label="IP地址" prop="ip_address">
          <el-input
            v-model="remoteDeviceForm.ip_address"
            placeholder="请输入远程设备IP地址"
          />
        </el-form-item>

        <el-form-item label="端口" prop="port">
          <el-input-number
            v-model="remoteDeviceForm.port"
            :min="1"
            :max="65535"
            placeholder="默认5555"
            style="width: 100%"
          />
        </el-form-item>

        <el-alert
          title="提示"
          type="info"
          :closable="false"
          style="margin-top: 10px"
        >
          <div>请确保：</div>
          <div>1. 远程设备已开启ADB调试</div>
          <div>2. 远程设备已开启网络ADB（adb tcpip 5555）</div>
          <div>3. 网络连接正常</div>
        </el-alert>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addRemoteDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="connecting"
            @click="connectRemoteDevice"
          >
            连接
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 设备详情对话框 -->
    <el-dialog
      v-model="deviceInfoDialogVisible"
      title="设备详情"
      width="600px"
    >
      <el-descriptions v-if="selectedDevice" :column="2" border>
        <el-descriptions-item label="设备名称">
          {{ selectedDevice.name || selectedDevice.device_id }}
        </el-descriptions-item>
        <el-descriptions-item label="设备序列号">
          {{ selectedDevice.device_id }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(selectedDevice.status)" size="small">
            {{ getStatusText(selectedDevice.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="锁定用户">
          {{ selectedDevice.locked_by_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="锁定时间">
          {{ selectedDevice.locked_at ? formatDate(selectedDevice.locked_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="Android版本">
          {{ selectedDevice.android_version || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="连接类型">
          <el-tag
            :type="getConnectionType(selectedDevice.connection_type) === 'local' ? 'primary' : 'warning'"
            size="small"
          >
            {{ getConnectionTypeName(selectedDevice.connection_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="IP地址">
          {{ selectedDevice.ip_address || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="端口">
          {{ selectedDevice.port || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="使用次数">
          {{ selectedDevice.usage_count || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatDate(selectedDevice.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDate(selectedDevice.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="deviceInfoDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import {
  getDeviceList,
  discoverDevices,
  lockDevice as apiLockDevice,
  unlockDevice as apiUnlockDevice,
  connectDevice,
  disconnectDevice as apiDisconnectDevice,
  deleteDevice
} from '@/api/app-automation'
import { getDeviceStatusType, getDeviceStatusText, formatDateTime } from '@/utils/app-automation-helpers'

// Refs
const remoteDeviceFormRef = ref(null)

// 响应式数据
const devices = ref([])
const loading = ref(false)
const refreshing = ref(false)
const connecting = ref(false)
const reconnectingDevices = ref({})
const addRemoteDialogVisible = ref(false)
const deviceInfoDialogVisible = ref(false)
const selectedDevice = ref(null)
const emptyText = ref('暂无设备，请点击刷新设备或添加远程设备')
const refreshTimer = ref(null)

const remoteDeviceForm = ref({
  ip_address: '',
  port: 5555
})

const remoteDeviceRules = {
  ip_address: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    {
      pattern: /^(\d{1,3}\.){3}\d{1,3}$/,
      message: '请输入有效的IP地址',
      trigger: 'blur'
    }
  ],
  port: [
    { required: true, message: '请输入端口号', trigger: 'blur' }
  ]
}

// 方法
const getDevices = async () => {
  loading.value = true
  try {
    const res = await getDeviceList({ page: 1, page_size: 1000 })
    devices.value = res.data.results || []
    if (devices.value.length === 0) {
      emptyText.value = '暂无设备，请点击刷新设备或添加远程设备'
    }
  } catch (error) {
    console.error('获取设备列表失败:', error)
    ElMessage.error('获取设备列表失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const refreshDevices = async () => {
  refreshing.value = true
  try {
    const res = await discoverDevices()
    if (res.data.success) {
      devices.value = res.data.devices || []
      ElMessage.success(res.data.message || '设备列表已刷新')
    } else {
      ElMessage.error(res.data.message || '刷新设备列表失败')
    }
  } catch (error) {
    console.error('刷新设备列表失败:', error)
    ElMessage.error('刷新设备列表失败: ' + (error.message || '未知错误'))
  } finally {
    refreshing.value = false
  }
}

const showAddRemoteDialog = () => {
  addRemoteDialogVisible.value = true
  remoteDeviceForm.value = {
    ip_address: '',
    port: 5555
  }
  if (remoteDeviceFormRef.value) {
    remoteDeviceFormRef.value.clearValidate()
  }
}

const connectRemoteDevice = async () => {
  if (!remoteDeviceFormRef.value) return
  
  remoteDeviceFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    connecting.value = true
    try {
      const res = await connectDevice({
        ip_address: remoteDeviceForm.value.ip_address,
        port: remoteDeviceForm.value.port
      })
      
      if (res.data.success) {
        ElMessage.success(res.data.message || '远程设备连接成功')
        addRemoteDialogVisible.value = false
        await getDevices()
      } else {
        ElMessage.error(res.data.message || '连接远程设备失败')
      }
    } catch (error) {
      console.error('连接远程设备失败:', error)
      ElMessage.error('连接远程设备失败: ' + (error.message || '未知错误'))
    } finally {
      connecting.value = false
    }
  })
}

const reconnectDevice = async (device) => {
  if (!device.ip_address || !device.port) {
    ElMessage.error('设备信息不完整，无法重连')
    return
  }

  reconnectingDevices.value[device.id] = true
  
  try {
    const res = await connectDevice({
      ip_address: device.ip_address,
      port: device.port
    })

    if (res.data.success) {
      ElMessage.success('设备重连成功')
      await getDevices()
    } else {
      ElMessage.error(res.data.message || '设备重连失败，请检查设备网络连接')
    }
  } catch (error) {
    console.error('设备重连失败:', error)
    ElMessage.error('设备重连失败，请检查设备网络连接')
  } finally {
    reconnectingDevices.value[device.id] = false
  }
}

const disconnectDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      `确定要断开设备 ${device.name || device.device_id} 的连接吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await apiDisconnectDevice(device.id)

    if (res.data.success) {
      ElMessage.success('设备已断开')
      await getDevices()
    } else {
      ElMessage.error(res.data.message || '断开设备失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('断开设备失败:', error)
      ElMessage.error('断开设备失败: ' + (error.message || '未知错误'))
    }
  }
}

const viewDeviceInfo = (device) => {
  selectedDevice.value = device
  deviceInfoDialogVisible.value = true
}

const lockDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      `确定要锁定设备 ${device.name || device.device_id} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await apiLockDevice(device.id)

    if (res.data.success) {
      ElMessage.success('设备已锁定')
      await getDevices()
    } else {
      ElMessage.error(res.data.message || '锁定设备失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('锁定设备失败:', error)
      ElMessage.error('锁定设备失败: ' + (error.message || '未知错误'))
    }
  }
}

const unlockDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      `确定要解锁设备 ${device.name || device.device_id} 吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await apiUnlockDevice(device.id)

    if (res.data.success) {
      ElMessage.success('设备已解锁')
      await getDevices()
    } else {
      ElMessage.error(res.data.message || '解锁设备失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('解锁设备失败:', error)
      ElMessage.error('解锁设备失败: ' + (error.message || '未知错误'))
    }
  }
}

const handleDeleteDevice = async (device) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备 ${device.name || device.device_id} 吗？删除后将无法恢复。`,
      '删除设备',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: false
      }
    )

    const res = await deleteDevice(device.id)

    if (res.status === 204 || res.status === 200) {
      ElMessage.success('设备已删除')
      await getDevices()
    } else {
      ElMessage.error(res.data?.message || '删除设备失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除设备失败:', error)
      ElMessage.error('删除设备失败: ' + (error.message || '未知错误'))
    }
  }
}

const formatDate = formatDateTime
const getStatusType = getDeviceStatusType
const getStatusText = getDeviceStatusText

const getConnectionType = (type) => {
  // emulator, remote_emulator, remote, usb 等
  if (type === 'emulator' || type === 'usb') {
    return 'local'
  }
  return 'remote'
}

const getConnectionTypeName = (type) => {
  const typeMap = {
    'emulator': '本地模拟器',
    'remote_emulator': '远程模拟器',
    'remote': '远程设备',
    'usb': 'USB连接'
  }
  return typeMap[type] || type
}

const isRemoteDevice = (type) => {
  return type === 'remote_emulator' || type === 'remote'
}

// 生命周期
onMounted(() => {
  getDevices()

  // 30秒自动刷新设备列表
  refreshTimer.value = setInterval(() => {
    getDevices()
  }, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})
</script>

<style scoped lang="scss">
.device-management {
  padding: 20px;
}

.device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h3 {
    margin: 0;
    font-size: 20px;
    color: #303133;
  }
}

.device-actions {
  display: flex;
  gap: 10px;
}

.dialog-footer {
  text-align: right;
}
</style>
