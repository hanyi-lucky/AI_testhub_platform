<template>
  <el-dialog
    v-model="visible"
    :title="t('apiTesting.dataFactory.select.title')"
    width="1000px"
    :close-on-click-modal="false"
    @close="handleClose"
    class="data-factory-dialog"
  >
    <div class="data-factory-selector">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane :label="t('apiTesting.dataFactory.select.byTag')" name="byTag">
          <div class="tag-selector">
            <el-form :inline="true" @submit.prevent="fetchRecordsByTag">
              <el-form-item :label="t('apiTesting.dataFactory.select.tag')">
                <el-select
                  v-model="selectedTag"
                  :placeholder="t('apiTesting.dataFactory.select.selectTag')"
                  filterable
                  allow-create
                  clearable
                >
                  <el-option
                    v-for="tag in availableTags"
                    :key="tag"
                    :label="tag"
                    :value="tag"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('apiTesting.dataFactory.select.toolCategory')">
                <el-select
                  v-model="filterCategory"
                  :placeholder="t('apiTesting.dataFactory.select.selectToolCategory')"
                  clearable
                  style="width: 200px"
                >
                  <el-option
                    v-for="cat in categories"
                    :key="cat.value"
                    :label="cat.label"
                    :value="cat.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchRecordsByTag">{{ t('apiTesting.dataFactory.select.search') }}</el-button>
              </el-form-item>
          </el-form>

          <el-table
            v-loading="loading"
            :data="records"
            stripe
            border
            @row-click="handleRowClick"
            class="records-table"
            height="400"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="tool_name_display" :label="t('apiTesting.dataFactory.select.toolName')" min-width="150" />
            <el-table-column prop="tool_category_display" :label="t('apiTesting.dataFactory.select.category')" min-width="100" />
            <el-table-column prop="created_at" :label="t('apiTesting.dataFactory.select.createdAt')" min-width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="tags" :label="t('apiTesting.dataFactory.select.tags')" min-width="150">
              <template #default="{ row }">
                <el-tag
                  v-for="tag in (row.tags || [])"
                  :key="tag"
                  size="small"
                  style="margin-right: 5px"
                >
                  {{ tag }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('apiTesting.dataFactory.select.operation')" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="previewRecord(row)">
                  {{ t('apiTesting.dataFactory.select.preview') }}
                </el-button>
                <el-button type="primary" link size="small" @click="selectRecord(row)">
                  {{ t('apiTesting.dataFactory.select.select') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-if="total > 0"
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
            class="pagination"
          />
          </div>
        </el-tab-pane>

        <el-tab-pane :label="t('apiTesting.dataFactory.select.byRecord')" name="byRecord">
          <div class="record-selector">
            <el-form :inline="true" @submit.prevent="fetchRecords">
              <el-form-item :label="t('apiTesting.dataFactory.select.toolName')">
                <el-input
                  v-model="filterToolName"
                  :placeholder="t('apiTesting.dataFactory.select.inputToolName')"
                  clearable
                  @clear="fetchRecords"
                />
              </el-form-item>
              <el-form-item :label="t('apiTesting.dataFactory.select.toolCategory')">
                <el-select
                  v-model="filterCategory"
                  :placeholder="t('apiTesting.dataFactory.select.selectToolCategory')"
                  clearable
                  style="width: 200px"
                >
                  <el-option
                    v-for="cat in categories"
                    :key="cat.value"
                    :label="cat.label"
                    :value="cat.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('apiTesting.dataFactory.select.tag')">
                <el-select
                  v-model="filterTag"
                  :placeholder="t('apiTesting.dataFactory.select.selectTag')"
                  filterable
                  allow-create
                  clearable
                >
                  <el-option
                    v-for="tag in availableTags"
                    :key="tag"
                    :label="tag"
                    :value="tag"
                  />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchRecords">{{ t('apiTesting.dataFactory.select.search') }}</el-button>
              </el-form-item>
            </el-form>

            <el-table
              v-loading="loading"
              :data="records"
              stripe
              border
              @row-click="handleRowClick"
              class="records-table"
              height="400"
            >
              <el-table-column type="selection" width="55" />
            <el-table-column prop="tool_name_display" :label="t('apiTesting.dataFactory.select.toolName')" min-width="150" />
            <el-table-column prop="tool_category_display" :label="t('apiTesting.dataFactory.select.category')" min-width="100" />
              <el-table-column prop="created_at" :label="t('apiTesting.dataFactory.select.createdAt')" min-width="180">
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column prop="tags" :label="t('apiTesting.dataFactory.select.tags')" min-width="150">
                <template #default="{ row }">
                  <el-tag
                    v-for="tag in (row.tags || [])"
                    :key="tag"
                    size="small"
                    style="margin-right: 5px"
                  >
                    {{ tag }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('apiTesting.dataFactory.select.operation')" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="previewRecord(row)">
                    {{ t('apiTesting.dataFactory.select.preview') }}
                  </el-button>
                  <el-button type="primary" link size="small" @click="selectRecord(row)">
                    {{ t('apiTesting.dataFactory.select.select') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              v-if="total > 0"
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handlePageChange"
              class="pagination"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="handleClose">{{ t('apiTesting.dataFactory.select.cancel') }}</el-button>
      <el-button type="primary" @click="handleConfirm" :disabled="!selectedRecord">
        {{ t('apiTesting.dataFactory.select.confirmSelect') }}
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="previewVisible"
    :title="t('apiTesting.dataFactory.select.dataPreview')"
    width="800px"
  >
    <div v-if="previewRecordData" class="preview-content">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.toolName')">
          {{ previewRecordData.tool_name_display || previewRecordData.tool_name }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.toolCategory')">
          {{ previewRecordData.tool_category_display }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.createdAt')">
          {{ formatDate(previewRecordData.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.tags')">
          <el-tag
            v-for="tag in (previewRecordData.tags || [])"
            :key="tag"
            size="small"
            style="margin-right: 5px"
          >
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.inputData')">
          <pre class="json-preview">{{ JSON.stringify(previewRecordData.input_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="t('apiTesting.dataFactory.select.outputData')">
          <pre class="json-preview">{{ JSON.stringify(previewRecordData.output_data, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'select'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref('byTag')
const selectedTag = ref('')
const filterToolName = ref('')
const filterCategory = ref('')
const filterTag = ref('')
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const selectedRecord = ref(null)
const previewVisible = ref(false)
const previewRecordData = ref(null)
const availableTags = ref([])

const categories = [
  { value: 'string', label: '字符工具' },
  { value: 'encoding', label: '编码工具' },
  { value: 'random', label: '随机工具' },
  { value: 'encryption', label: '加密工具' },
  { value: 'test_data', label: '测试数据' },
  { value: 'json', label: 'JSON工具' },
  { value: 'crontab', label: 'Crontab工具' }
]

const fetchAvailableTags = async () => {
  try {
    const response = await axios.get('/api/data-factory/tags/')
    availableTags.value = response.data.tags || []
  } catch (error) {
    console.error('获取标签列表失败:', error)
    ElMessage.error('获取标签列表失败')
  }
}

const fetchRecordsByTag = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (selectedTag.value) {
      params.tags__contains = selectedTag.value
    }
    
    if (filterCategory.value) {
      params.tool_category = filterCategory.value
    }
    
    const response = await axios.get('/api/data-factory/', { params })
    records.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    console.error('获取记录失败:', error)
    const errorMsg = error.response?.data?.error || error.response?.data?.detail || error.message || '获取记录失败'
    ElMessage.error(errorMsg)
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (filterToolName.value) {
      params.tool_name__icontains = filterToolName.value
    }
    
    if (filterCategory.value) {
      params.tool_category = filterCategory.value
    }
    
    if (filterTag.value) {
      params.tags__contains = filterTag.value
    }
    
    const response = await axios.get('/api/data-factory/', { params })
    records.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    console.error('获取记录失败:', error)
    const errorMsg = error.response?.data?.error || error.response?.data?.detail || error.message || '获取记录失败'
    ElMessage.error(errorMsg)
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const handleTabChange = (tab) => {
  currentPage.value = 1
  if (tab === 'byTag') {
    fetchRecordsByTag()
  } else {
    fetchRecords()
  }
}

const handleTagChange = () => {
  currentPage.value = 1
  fetchRecordsByTag()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  if (activeTab.value === 'byTag') {
    fetchRecordsByTag()
  } else {
    fetchRecords()
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  if (activeTab.value === 'byTag') {
    fetchRecordsByTag()
  } else {
    fetchRecords()
  }
}

const handleRowClick = (row) => {
  selectedRecord.value = row
}

const selectRecord = (record) => {
  selectedRecord.value = record
  emit('select', record)
  visible.value = false
}

const previewRecord = (record) => {
  previewRecordData.value = record
  previewVisible.value = true
}

const handleConfirm = () => {
  if (selectedRecord.value) {
    emit('select', selectedRecord.value)
    visible.value = false
  }
}

const handleClose = () => {
  visible.value = false
  selectedRecord.value = null
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    fetchAvailableTags()
    fetchRecordsByTag()
  }
})
</script>

<style scoped lang="scss">
:deep(.data-factory-dialog) {
  .el-dialog__body {
    max-height: 60vh;
    overflow-y: auto;
    padding: 20px;
  }
}

.data-factory-selector {
  display: flex;
  flex-direction: column;
  
  .tag-selector,
  .record-selector {
    display: flex;
    flex-direction: column;
    
    .el-form {
      margin-bottom: 20px;
      flex-shrink: 0;
    }
  }
  
  .records-table {
    margin-bottom: 20px;
    
    :deep(.el-table__row) {
      cursor: pointer;
      
      &:hover {
        background-color: #f5f7fa;
      }
    }
  }
  
  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
    padding: 10px 0;
    flex-shrink: 0;
  }
}

.preview-content {
  .json-preview {
    max-height: 300px;
    overflow: auto;
    overflow-x: auto;
    overflow-y: auto;
    background: #f5f7fa;
    padding: 10px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    word-break: break-all;
  }
}
</style>
