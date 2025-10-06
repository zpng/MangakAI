/**
 * API service for MangakAI frontend
 */
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds timeout for regular requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for session ID
apiClient.interceptors.request.use((config) => {
  const sessionId = localStorage.getItem('mangakai_session_id');
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId;
    // Also add as query parameter for some endpoints
    if (config.method === 'get' || config.method === 'delete') {
      config.params = { ...config.params, session_id: sessionId };
    }
  }
  return config;
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

/**
 * Generate session ID if not exists
 */
export const getOrCreateSessionId = () => {
  let sessionId = localStorage.getItem('mangakai_session_id');
  if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('mangakai_session_id', sessionId);
  }
  return sessionId;
};

/**
 * Async Manga Generation API
 */

// Create async manga generation task
export const createMangaTask = async (data) => {
  const sessionId = getOrCreateSessionId();
  return apiClient.post('/api/async/generate-manga', {
    ...data,
    session_id: sessionId
  });
};

// Create manga task from file
export const createMangaTaskFromFile = async (file, options = {}) => {
  const sessionId = getOrCreateSessionId();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);
  
  // Add other options
  Object.keys(options).forEach(key => {
    if (options[key] !== null && options[key] !== undefined) {
      formData.append(key, options[key]);
    }
  });

  return apiClient.post('/api/async/generate-manga-from-file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 60000, // 1 minute timeout for file uploads
  });
};

// Get task status
export const getTaskStatus = async (taskId) => {
  return apiClient.get(`/api/async/task/${taskId}/status`);
};

// Regenerate panel
export const regeneratePanel = async (taskId, panelNumber, modificationRequest, referenceImage = null) => {
  const formData = new FormData();
  formData.append('modification_request', modificationRequest);
  
  if (referenceImage) {
    formData.append('reference_image', referenceImage);
  }

  return apiClient.post(`/api/async/task/${taskId}/regenerate-panel/${panelNumber}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Get user tasks
export const getUserTasks = async (limit = 10, offset = 0) => {
  const sessionId = getOrCreateSessionId();
  return apiClient.get('/api/async/tasks', {
    params: { session_id: sessionId, limit, offset }
  });
};

// Cancel task
export const cancelTask = async (taskId) => {
  return apiClient.delete(`/api/async/task/${taskId}`);
};

/**
 * Legacy API (for backward compatibility)
 */

// Generate manga (legacy sync method)
export const generateManga = async (data) => {
  return apiClient.post('/api/generate-manga', data, {
    timeout: 300000, // 5 minutes timeout for sync generation
  });
};

// Generate manga from file (legacy)
export const generateMangaFromFile = async (file, options = {}) => {
  const formData = new FormData();
  formData.append('file', file);
  
  Object.keys(options).forEach(key => {
    if (options[key] !== null && options[key] !== undefined) {
      formData.append(key, options[key]);
    }
  });

  return apiClient.post('/api/generate-manga-from-file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000, // 5 minutes timeout
  });
};

// Regenerate panel (legacy)
export const regeneratePanelLegacy = async (panelNumber, modificationRequest, replaceOriginal = false, referenceImage = null) => {
  const formData = new FormData();
  formData.append('panel_number', panelNumber);
  formData.append('modification_request', modificationRequest);
  formData.append('replace_original', replaceOriginal);
  
  if (referenceImage) {
    formData.append('reference_image', referenceImage);
  }

  return apiClient.post('/api/regenerate-panel', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

/**
 * Utility API
 */

// Get style options
export const getStyleOptions = async () => {
  return apiClient.get('/api/style-options');
};

// Get examples
export const getExamples = async () => {
  return apiClient.get('/api/examples');
};

// Get specific example
export const getExample = async (exampleName) => {
  return apiClient.get(`/api/examples/${exampleName}`);
};

// Create PDF
export const createPDF = async () => {
  return apiClient.post('/api/create-pdf');
};

// Get current panels
export const getCurrentPanels = async () => {
  return apiClient.get('/api/current-panels');
};

/**
 * Health checks
 */

// Check API health
export const checkHealth = async () => {
  return apiClient.get('/health');
};

// Check async API health
export const checkAsyncHealth = async () => {
  return apiClient.get('/api/async/health');
};

// Check WebSocket health
export const checkWebSocketHealth = async () => {
  return apiClient.get('/ws/health');
};

/**
 * Error handling utilities
 */

export const handleApiError = (error) => {
  if (error.response) {
    // Server responded with error status
    const { status, data } = error.response;
    
    switch (status) {
      case 400:
        return `请求错误: ${data.detail || '参数无效'}`;
      case 401:
        return '未授权访问';
      case 403:
        return '访问被禁止';
      case 404:
        return '资源不存在';
      case 429:
        return '请求过于频繁，请稍后重试';
      case 500:
        return `服务器错误: ${data.detail || '内部错误'}`;
      case 503:
        return '服务暂时不可用';
      default:
        return `请求失败 (${status}): ${data.detail || '未知错误'}`;
    }
  } else if (error.request) {
    // Network error
    return '网络连接失败，请检查网络设置';
  } else {
    // Other error
    return `请求失败: ${error.message}`;
  }
};

/**
 * Task status helpers
 */

export const TASK_STATUS = {
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  SCENE_GENERATION: 'SCENE_GENERATION',
  IMAGE_GENERATION: 'IMAGE_GENERATION',
  PANEL_PROCESSING: 'PANEL_PROCESSING',
  UPLOADING: 'UPLOADING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED'
};

export const getStatusMessage = (status, progress = 0, currentPanel = 0, totalPanels = 0) => {
  switch (status) {
    case TASK_STATUS.PENDING:
      return '等待处理...';
    case TASK_STATUS.PROCESSING:
      return '开始处理...';
    case TASK_STATUS.SCENE_GENERATION:
      return '正在分析故事并生成场景描述...';
    case TASK_STATUS.IMAGE_GENERATION:
      return `正在生成图片... (${progress}%)`;
    case TASK_STATUS.PANEL_PROCESSING:
      return `正在处理第 ${currentPanel}/${totalPanels} 个面板...`;
    case TASK_STATUS.UPLOADING:
      return '正在上传图片...';
    case TASK_STATUS.COMPLETED:
      return '生成完成！';
    case TASK_STATUS.FAILED:
      return '生成失败';
    case TASK_STATUS.CANCELLED:
      return '任务已取消';
    default:
      return '未知状态';
  }
};

export const isTaskActive = (status) => {
  return [
    TASK_STATUS.PENDING,
    TASK_STATUS.PROCESSING,
    TASK_STATUS.SCENE_GENERATION,
    TASK_STATUS.IMAGE_GENERATION,
    TASK_STATUS.PANEL_PROCESSING,
    TASK_STATUS.UPLOADING
  ].includes(status);
};

export const isTaskCompleted = (status) => {
  return status === TASK_STATUS.COMPLETED;
};

export const isTaskFailed = (status) => {
  return [TASK_STATUS.FAILED, TASK_STATUS.CANCELLED].includes(status);
};