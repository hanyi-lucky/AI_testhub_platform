<template>
  <div class="app-automation-index">
    <el-card shadow="never">
      <div class="welcome-section">
        <h1>APP 自动化测试</h1>
        <p>基于 Airtest 的 Android APP 自动化测试平台</p>
      </div>
      
      <div class="features-grid">
        <el-card shadow="hover" class="feature-card" @click="$router.push('/app-automation/dashboard')">
          <div class="feature-icon bg-blue">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="feature-title">Dashboard</div>
          <div class="feature-desc">查看统计数据和执行概览</div>
        </el-card>
        
        <el-card shadow="hover" class="feature-card" @click="$router.push('/app-automation/devices')">
          <div class="feature-icon bg-green">
            <el-icon><Cellphone /></el-icon>
          </div>
          <div class="feature-title">设备管理</div>
          <div class="feature-desc">管理 Android 设备和模拟器</div>
        </el-card>
        
        <el-card shadow="hover" class="feature-card" @click="$router.push('/app-automation/elements')">
          <div class="feature-icon bg-purple">
            <el-icon><Picture /></el-icon>
          </div>
          <div class="feature-title">元素管理</div>
          <div class="feature-desc">管理UI元素（图片/坐标/区域）</div>
        </el-card>
        
        <el-card shadow="hover" class="feature-card" @click="$router.push('/app-automation/test-cases')">
          <div class="feature-icon bg-orange">
            <el-icon><Document /></el-icon>
          </div>
          <div class="feature-title">测试用例</div>
          <div class="feature-desc">创建和管理测试用例</div>
        </el-card>
        
        <el-card shadow="hover" class="feature-card" @click="$router.push('/app-automation/executions')">
          <div class="feature-icon bg-red">
            <el-icon><Aim /></el-icon>
          </div>
          <div class="feature-title">执行记录</div>
          <div class="feature-desc">查看测试执行结果</div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { DataAnalysis, Cellphone, Picture, Document, Aim } from '@element-plus/icons-vue'
</script>

<style scoped lang="scss">
.app-automation-index {
  padding: 20px;
}

.welcome-section {
  text-align: center;
  margin-bottom: 40px;
  
  h1 {
    font-size: 32px;
    color: #303133;
    margin-bottom: 10px;
  }
  
  p {
    font-size: 16px;
    color: #909399;
  }
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  
  .feature-card {
    cursor: pointer;
    transition: all 0.3s;
    text-align: center;
    padding: 20px;
    
    &:hover {
      transform: translateY(-5px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    .feature-icon {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      margin: 0 auto 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 36px;
      color: white;
      
      &.bg-blue { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
      &.bg-green { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
      &.bg-purple { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
      &.bg-orange { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }
      &.bg-red { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%); }
    }
    
    .feature-title {
      font-size: 18px;
      font-weight: bold;
      color: #303133;
      margin-bottom: 10px;
    }
    
    .feature-desc {
      font-size: 14px;
      color: #909399;
      line-height: 1.6;
    }
  }
}
</style>
