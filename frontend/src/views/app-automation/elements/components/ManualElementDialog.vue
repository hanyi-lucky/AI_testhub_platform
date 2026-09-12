<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑元素' : '新增元素'"
    width="700px"
    @close="handleClose"
  >
    <el-form :model="formData" ref="formRef" label-width="120px" :rules="rules">
      <el-form-item label="元素名称" prop="name" required>
        <el-input v-model="formData.name" placeholder="如：登录按钮" />
      </el-form-item>

      <el-form-item label="所属项目">
        <el-select v-model="formData.project" placeholder="请选择项目" clearable filterable style="width: 100%">
          <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="元素类型" prop="element_type" required>
        <el-radio-group v-model="formData.element_type" @change="handleTypeChange">
          <el-radio value="image">图片元素</el-radio>
          <el-radio value="pos">坐标元素</el-radio>
          <el-radio value="region">区域元素</el-radio>
        </el-radio-group>
      </el-form-item>
      
      <el-form-item label="标签">
        <el-select
          v-model="formData.tags"
          multiple
          filterable
          allow-create
          placeholder="输入标签后回车"
          style="width: 100%"
        >
          <el-option label="登录" value="登录" />
        </el-select>
        <div style="color: #909399; font-size: 12px; margin-top: 5px;">
          💡 提示：输入标签回车创建
        </div>
      </el-form-item>
      
      <!-- 图片类型配置 -->
      <template v-if="formData.element_type === 'image'">
        <el-divider content-position="left">图片配置</el-divider>
        
        <el-form-item label="图片分类" required>
          <div style="display: flex; gap: 10px;">
            <el-select 
              v-model="formData.config.image_category"
              placeholder="选择分类"
              filterable
              style="flex: 1;"
            >
              <el-option 
                v-for="cat in imageCategories" 
                :key="cat" 
                :label="cat" 
                :value="cat"
              >
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                  <span>{{ cat }}</span>
                  <el-button
                    v-if="cat !== 'common'"
                    type="danger"
                    size="small"
                    link
                    :icon="Delete"
                    @click.stop="handleDeleteCategory(cat)"
                    title="删除分类"
                    style="padding: 0; margin-left: 8px;"
                  />
                </div>
              </el-option>
            </el-select>
            <el-button 
              type="primary" 
              :icon="Plus" 
              @click="showCreateCategoryDialog"
              title="创建新分类"
            />
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：图片将保存到 Template/&lt;分类&gt;/ 目录下
          </div>
        </el-form-item>
        
        <el-form-item label="元素图片">
          <!-- 编辑模式：显示当前图片和更换选项 -->
          <div v-if="isEdit && formData.config.image_path" class="current-image-section">
            <div style="color: #606266; font-size: 14px; margin-bottom: 10px; font-weight: 500;">
              📷 当前图片
            </div>
            
            <!-- 图片预览 -->
            <div class="image-preview-box">
              <el-image 
                :key="imageRefreshKey"
                :src="currentImageUrl" 
                style="max-width: 200px; max-height: 150px; border-radius: 4px;"
                fit="contain"
                :preview-src-list="[currentImageUrl]"
              >
                <template #error>
                  <div class="image-error">
                    <el-icon :size="50"><Picture /></el-icon>
                    <div>加载失败</div>
                  </div>
                </template>
              </el-image>
            </div>
            
            <!-- 图片信息 -->
            <div class="image-info-box">
              <div class="info-item">
                <el-icon><Folder /></el-icon>
                <span>{{ formData.config.image_path }}</span>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <el-space style="margin-top: 10px">
              <el-button 
                v-if="!showUpload" 
                type="primary" 
                size="small"
                :icon="Upload"
                @click="handleChangeImage"
              >
                更换图片
              </el-button>
              <el-button 
                v-if="showUpload"
                size="small"
                @click="cancelUpload"
              >
                取消更换
              </el-button>
            </el-space>
            
            <!-- 隐藏的 upload 组件 -->
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :on-change="handleImageChange"
              :limit="1"
              :show-file-list="false"
              accept="image/png,image/jpg,image/jpeg"
              style="display: none;"
            />
            
            <!-- 新图片预览区域 -->
            <div v-if="showUpload && imagePreview" style="margin-top: 15px">
              <div style="color: #67C23A; font-size: 14px; margin-bottom: 10px; font-weight: 500;">
                <el-icon><SuccessFilled /></el-icon> 新图片
              </div>
              
              <div class="image-preview-box" style="border-color: #67C23A;">
                <el-image 
                  :src="imagePreview" 
                  style="max-width: 200px; max-height: 150px; border-radius: 4px;"
                  fit="contain"
                  :preview-src-list="[imagePreview]"
                />
              </div>
              
              <div class="image-info-box">
                <div class="info-item">
                  <el-icon><Document /></el-icon>
                  <span>{{ imageFile?.name || '新选择的图片' }}</span>
                </div>
              </div>
              
              <div style="color: #67C23A; font-size: 12px; margin-top: 8px;">
                💡 保存后将替换当前图片
              </div>
            </div>
          </div>
          
          <!-- 新建模式：直接显示上传 -->
          <div v-else>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :on-change="handleImageChange"
              :on-exceed="handleExceed"
              :limit="1"
              accept="image/png,image/jpg,image/jpeg"
              list-type="picture"
            >
              <el-button type="primary" size="small" :icon="Upload">
                选择图片
              </el-button>
              <template #tip>
                <div style="color: #909399; font-size: 12px;">
                  支持 PNG、JPG 格式
                </div>
              </template>
            </el-upload>
            
            <div v-if="imagePreview" style="margin-top: 10px">
              <el-image :src="imagePreview" style="max-width: 200px" fit="contain" />
            </div>
          </div>
        </el-form-item>
        
        <el-form-item label="匹配阈值">
          <el-slider
            v-model="formData.config.image_threshold"
            :min="0.5"
            :max="1.0"
            :step="0.05"
            show-input
            :format-tooltip="val => val.toFixed(2)"
          />
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：阈值越高匹配越严格（推荐 0.7-0.8），越低越宽松但可能误匹配
          </div>
        </el-form-item>
        
        <el-form-item label="颜色模式">
          <el-switch
            v-model="formData.config.rgb"
            active-text="RGB彩色"
            inactive-text="灰度"
          />
          <div style="color: #909399; font-size: 12px; margin-top: 5px;">
            💡 提示：RGB彩色适用于彩色界面，灰度适用于单色或对颜色不敏感的场景
          </div>
        </el-form-item>
      </template>
      
      <!-- 坐标类型配置 -->
      <template v-if="formData.element_type === 'pos'">
        <el-divider content-position="left">坐标配置</el-divider>
        
        <el-form-item label="X坐标" required>
          <el-input-number v-model="formData.config.x" :min="0" placeholder="横坐标" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Y坐标" required>
          <el-input-number v-model="formData.config.y" :min="0" placeholder="纵坐标" style="width: 100%" />
        </el-form-item>
      </template>
      
      <!-- 区域类型配置 -->
      <template v-if="formData.element_type === 'region'">
        <el-divider content-position="left">区域配置</el-divider>
        
        <el-form-item label="左上角坐标" required>
          <el-space>
            <el-input-number v-model="formData.config.x1" placeholder="X1" style="width: 150px" />
            <el-input-number v-model="formData.config.y1" placeholder="Y1" style="width: 150px" />
          </el-space>
        </el-form-item>
        
        <el-form-item label="右下角坐标" required>
          <el-space>
            <el-input-number v-model="formData.config.x2" placeholder="X2" style="width: 150px" />
            <el-input-number v-model="formData.config.y2" placeholder="Y2" style="width: 150px" />
          </el-space>
        </el-form-item>
      </template>
    </el-form>
    
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
    </template>
  </el-dialog>
  
  <!-- 创建图片分类对话框 -->
  <el-dialog
    v-model="createCategoryVisible"
    title="创建图片分类"
    width="400px"
  >
    <el-form>
      <el-form-item label="分类名称">
        <el-input 
          v-model="newCategoryName" 
          placeholder="如：button, icon, menu"
          @keyup.enter="handleCreateCategory"
        />
        <div style="color: #909399; font-size: 12px; margin-top: 5px;">
          💡 只能包含字母、数字、下划线和中划线
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createCategoryVisible = false">取消</el-button>
      <el-button type="primary" @click="handleCreateCategory" :loading="creatingCategory">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Upload, Document, Folder, SuccessFilled, Picture } from '@element-plus/icons-vue'
import {
  uploadAppElementImage,
  createAppElement,
  updateAppElement,
  getAppImageCategories,
  createAppImageCategory,
  deleteAppImageCategory
} from '@/api/app-automation'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  editData: {
    type: Object,
    default: null
  },
  projectList: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'success'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const isEdit = computed(() => !!props.editData)

const formRef = ref(null)
const uploadRef = ref(null)
const submitting = ref(false)
const imageFile = ref(null)
const imagePreview = ref('')
const showUpload = ref(false)
const imageCategories = ref([])
const createCategoryVisible = ref(false)
const newCategoryName = ref('')
const creatingCategory = ref(false)

// 当前图片 URL（用于编辑模式）
const imageRefreshKey = ref(0)
const currentImageUrl = computed(() => {
  if (props.editData?.id && props.editData?.config?.image_path) {
    // 添加时间戳参数，避免浏览器缓存
    return `/api/app-automation/elements/${props.editData.id}/preview/?t=${imageRefreshKey.value}`
  }
  return ''
})

const formData = reactive({
  name: '',
  element_type: 'image',
  project: null,
  tags: [],
  config: {
    image_category: 'common',
    image_threshold: 0.7,
    rgb: false,
    x: 0,
    y: 0,
    x1: 0,
    y1: 0,
    x2: 0,
    y2: 0,
    image_path: '',
    file_hash: ''
  }
})

const rules = {
  name: [
    { required: true, message: '请输入元素名称', trigger: 'blur' }
  ],
  element_type: [
    { required: true, message: '请选择元素类型', trigger: 'change' }
  ]
}

const handleTypeChange = () => {
  formData.config = {
    image_category: 'common',
    image_threshold: 0.7,
    rgb: false,
    x: 0,
    y: 0,
    x1: 0,
    y1: 0,
    x2: 0,
    y2: 0,
    image_path: '',
    file_hash: ''
  }
  imageFile.value = null
  imagePreview.value = ''
}

const handleImageChange = (file) => {
  if (!file || !file.raw) return
  
  imageFile.value = file.raw
  
  const reader = new FileReader()
  reader.onload = (e) => {
    // readAsDataURL 返回的是 string 类型
    if (e.target && typeof e.target.result === 'string') {
      imagePreview.value = e.target.result
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  
  reader.readAsDataURL(file.raw)
}

const handleExceed = () => {
  ElMessage.warning('最多只能上传 1 个图片文件')
}

const handleChangeImage = async () => {
  imagePreview.value = ''
  imageFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  
  showUpload.value = true
  
  await nextTick()
  
  if (uploadRef.value) {
    const uploadElement = uploadRef.value.$el
    const inputElement = uploadElement.querySelector('input[type="file"]')
    if (inputElement) {
      inputElement.value = ''
      inputElement.click()
    }
  }
}

const cancelUpload = () => {
  showUpload.value = false
  imagePreview.value = ''
  imageFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    submitting.value = true
    
    // 图片类型需要先上传图片
    if (formData.element_type === 'image') {
      if (!isEdit.value && !imageFile.value) {
        ElMessage.warning('请选择图片文件')
        submitting.value = false
        return
      }
      
      // 上传图片（如果有新图片）
      if (imageFile.value) {
        const { data: uploadData } = await uploadAppElementImage(
          imageFile.value,
          formData.config.image_category || 'common',
          props.editData?.id || null
        )
        
        if (uploadData.success) {
          formData.config.image_path = uploadData.data.image_path
          formData.config.file_hash = uploadData.data.file_hash
        } else {
          let errorMessage = uploadData.message || '上传图片失败'
          if (uploadData.detail) {
            errorMessage += `\n\n${uploadData.detail}`
          }
          if (uploadData.suggestion) {
            errorMessage += `\n\n💡 建议：${uploadData.suggestion}`
          }
          
          ElMessage.error({
            message: errorMessage,
            duration: 8000,
            showClose: true
          })
          submitting.value = false
          return
        }
      }
    }
    
    // 准备提交数据
    const submitData = {
      name: formData.name,
      element_type: formData.element_type,
      project: formData.project || null,
      tags: formData.tags,
      config: {}
    }
    
    // 根据元素类型只包含必要的配置字段
    if (formData.element_type === 'image') {
      submitData.config = {
        image_category: formData.config.image_category || 'common',
        image_threshold: formData.config.image_threshold,
        rgb: formData.config.rgb,
        image_path: formData.config.image_path || '',
        file_hash: formData.config.file_hash || ''
      }
    } else if (formData.element_type === 'pos') {
      submitData.config = {
        x: formData.config.x,
        y: formData.config.y
      }
    } else if (formData.element_type === 'region') {
      submitData.config = {
        x1: formData.config.x1,
        y1: formData.config.y1,
        x2: formData.config.x2,
        y2: formData.config.y2
      }
    }
    
    // 创建或更新元素
    if (isEdit.value) {
      await updateAppElement(props.editData.id, submitData)
    } else {
      await createAppElement(submitData)
    }
    
    ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
    emit('success')
    handleClose()
  } catch (error) {
    console.error('提交失败:', error)
    if (error !== 'validation failed') {
      ElMessage.error('操作失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleClose = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  
  imageFile.value = null
  imagePreview.value = ''
  showUpload.value = false
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  
  Object.assign(formData, {
    name: '',
    element_type: 'image',
    project: null,
    tags: [],
    config: {
      image_category: 'common',
      image_threshold: 0.7,
      rgb: false,
      x: 0,
      y: 0,
      x1: 0,
      y1: 0,
      x2: 0,
      y2: 0,
      image_path: '',
      file_hash: ''
    }
  })
  
  emit('update:modelValue', false)
}

// 监听对话框打开/关闭
watch(() => props.modelValue, (newVal) => {
  if (newVal && props.editData) {
    // 手动同步 formData（防止 watch(editData) 不触发）
    if (props.editData.config) {
      formData.config.image_path = props.editData.config.image_path || ''
      formData.config.file_hash = props.editData.config.file_hash || ''
    }
    
    // 更新图片刷新key，强制重新加载图片
    imageRefreshKey.value = Date.now()
  }
})

// 监听编辑数据
watch(() => props.editData, (data) => {
  if (data) {
    formData.name = data.name || ''
    formData.element_type = data.element_type || 'image'
    formData.project = data.project || null
    formData.tags = data.tags ? [...data.tags] : []
    
    if (data.config) {
      formData.config = {
        image_category: data.config.image_category || 'common',
        image_threshold: data.config.image_threshold || 0.7,
        rgb: data.config.rgb !== undefined ? data.config.rgb : false,
        x: data.config.x || 0,
        y: data.config.y || 0,
        x1: data.config.x1 || 0,
        y1: data.config.y1 || 0,
        x2: data.config.x2 || 0,
        y2: data.config.y2 || 0,
        image_path: data.config.image_path || '',
        file_hash: data.config.file_hash || ''
      }
    }
    
    imagePreview.value = ''
    imageFile.value = null
    showUpload.value = false
    
    // 更新图片刷新key，强制重新加载图片
    imageRefreshKey.value = Date.now()
  }
}, { immediate: true })

// 加载图片分类列表
const loadImageCategories = async () => {
  try {
    const { data } = await getAppImageCategories()
    if (data.success && Array.isArray(data.data)) {
      imageCategories.value = data.data.map(cat => cat.name || cat)
    }
  } catch (error) {
    console.error('加载图片分类失败:', error)
    imageCategories.value = ['common']
  }
}

// 显示创建分类对话框
const showCreateCategoryDialog = () => {
  newCategoryName.value = ''
  createCategoryVisible.value = true
}

// 创建新分类
const handleCreateCategory = async () => {
  if (!newCategoryName.value.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  
  try {
    creatingCategory.value = true
    const { data } = await createAppImageCategory(newCategoryName.value.trim())
    
    if (data.success) {
      ElMessage.success('创建成功')
      await loadImageCategories()
      formData.config.image_category = data.data.name
      createCategoryVisible.value = false
    } else {
      ElMessage.error(data.message || '创建失败')
    }
  } catch (error) {
    console.error('创建分类失败:', error)
    ElMessage.error('创建失败')
  } finally {
    creatingCategory.value = false
  }
}

// 删除分类
const handleDeleteCategory = async (categoryName) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分类 "${categoryName}" 吗？只能删除空目录。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    const { data } = await deleteAppImageCategory(categoryName)
    
    if (data.success) {
      ElMessage.success('删除成功')
      await loadImageCategories()
      if (formData.config.image_category === categoryName) {
        formData.config.image_category = 'common'
      }
    } else {
      ElMessage.error(data.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除分类失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadImageCategories()
})
</script>

<style scoped>
.el-divider {
  margin: 10px 0;
}

.current-image-section {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.image-preview-box {
  display: inline-block;
  padding: 10px;
  background: white;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px;
  color: #909399;
  font-size: 12px;
}

.image-info-box {
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 0;
}

.info-item .el-icon {
  color: #909399;
}
</style>
