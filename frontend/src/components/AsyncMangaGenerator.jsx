/**
 * Async Manga Generator Component
 * Handles asynchronous manga generation with real-time progress updates
 */
import React, { useState, useEffect, useRef } from 'react';
import { Upload, Download, RefreshCw, FileText, Image, Wand2, X, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import websocketService from '../services/websocket';
import { 
  createMangaTask, 
  createMangaTaskFromFile, 
  getTaskStatus, 
  regeneratePanel,
  getUserTasks,
  cancelTask,
  handleApiError,
  getStatusMessage,
  isTaskActive,
  isTaskCompleted,
  isTaskFailed,
  TASK_STATUS
} from '../services/api';

const AsyncMangaGenerator = () => {
  // Form states
  const [storyText, setStoryText] = useState('');
  const [numScenes, setNumScenes] = useState(5);
  const [selectedStyles, setSelectedStyles] = useState({
    art_style: 'None',
    mood: 'None',
    color_palette: 'None',
    character_style: 'None',
    line_style: 'None',
    composition: 'None'
  });
  const [additionalNotes, setAdditionalNotes] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);

  // Task states
  const [currentTask, setCurrentTask] = useState(null);
  const [taskHistory, setTaskHistory] = useState([]);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [panels, setPanels] = useState([]);
  const [error, setError] = useState('');

  // UI states
  const [isGenerating, setIsGenerating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  // Regeneration states
  const [regeneratingPanel, setRegeneratingPanel] = useState(null);
  const [modificationRequest, setModificationRequest] = useState('');
  const [referenceImage, setReferenceImage] = useState(null);

  // Refs
  const fileInputRef = useRef(null);
  const referenceInputRef = useRef(null);

  useEffect(() => {
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Load task history
    loadTaskHistory();

    // Cleanup on unmount
    return () => {
      websocketService.disconnect();
    };
  }, []);

  const initializeWebSocket = async () => {
    try {
      await websocketService.connect();
      setWsConnected(true);

      // Set up event listeners
      websocketService.on('progress_update', handleProgressUpdate);
      websocketService.on('connected', () => setWsConnected(true));
      websocketService.on('disconnected', () => setWsConnected(false));
      websocketService.on('error', (error) => {
        console.error('WebSocket error:', error);
        setError('实时连接出现问题，可能无法接收进度更新');
      });

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setWsConnected(false);
      setError('无法建立实时连接，将使用轮询方式获取进度');
    }
  };

  const handleProgressUpdate = (data) => {
    const { task_id, status, progress, message, panels: updatedPanels, current_panel, total_panels } = data;

    if (currentTask && task_id === currentTask.task_id) {
      setStatus(status);
      setProgress(progress || 0);
      setStatusMessage(message || getStatusMessage(status, progress, current_panel, total_panels));

      if (updatedPanels) {
        setPanels(updatedPanels);
      }

      if (isTaskCompleted(status) || isTaskFailed(status)) {
        setIsGenerating(false);
        loadTaskHistory(); // Refresh history
      }
    }
  };

  const loadTaskHistory = async () => {
    try {
      const response = await getUserTasks(10, 0);
      setTaskHistory(response.data.tasks);
    } catch (error) {
      console.error('Failed to load task history:', error);
    }
  };

  const handleGenerateManga = async () => {
    if (!storyText.trim()) {
      setError('请输入故事内容');
      return;
    }

    try {
      setIsGenerating(true);
      setError('');
      setProgress(0);
      setPanels([]);

      const taskData = {
        story_text: storyText,
        num_scenes: numScenes,
        ...selectedStyles,
        additional_notes: additionalNotes
      };

      const response = await createMangaTask(taskData);
      const task = response.data;

      setCurrentTask(task);
      setStatus(task.status);
      setStatusMessage('任务已创建，正在处理中...');

      // Subscribe to task updates via WebSocket
      if (wsConnected) {
        websocketService.subscribeToTask(task.task_id);
      } else {
        // Fallback to polling if WebSocket is not available
        startPolling(task.task_id);
      }

    } catch (error) {
      setIsGenerating(false);
      setError(handleApiError(error));
    }
  };

  const handleFileUpload = async () => {
    if (!uploadedFile) {
      setError('请选择文件');
      return;
    }

    try {
      setIsGenerating(true);
      setError('');
      setProgress(0);
      setPanels([]);

      const options = {
        num_scenes: numScenes,
        ...selectedStyles,
        additional_notes: additionalNotes
      };

      const response = await createMangaTaskFromFile(uploadedFile, options);
      const task = response.data;

      setCurrentTask(task);
      setStatus(task.status);
      setStatusMessage('任务已创建，正在处理中...');

      // Subscribe to task updates
      if (wsConnected) {
        websocketService.subscribeToTask(task.task_id);
      } else {
        startPolling(task.task_id);
      }

    } catch (error) {
      setIsGenerating(false);
      setError(handleApiError(error));
    }
  };

  const startPolling = (taskId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await getTaskStatus(taskId);
        const taskData = response.data;

        setStatus(taskData.status);
        setProgress(taskData.progress);
        setStatusMessage(getStatusMessage(taskData.status, taskData.progress, taskData.current_panel, taskData.total_panels));
        setPanels(taskData.panels);

        if (isTaskCompleted(taskData.status) || isTaskFailed(taskData.status)) {
          clearInterval(pollInterval);
          setIsGenerating(false);
          loadTaskHistory();
        }

      } catch (error) {
        console.error('Polling error:', error);
        clearInterval(pollInterval);
        setIsGenerating(false);
        setError('获取任务状态失败');
      }
    }, 3000); // Poll every 3 seconds

    // Stop polling after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
    }, 600000);
  };

  const handleRegeneratePanel = async (panelNumber) => {
    if (!modificationRequest.trim()) {
      setError('请输入修改要求');
      return;
    }

    try {
      setRegeneratingPanel(panelNumber);
      setError('');

      await regeneratePanel(currentTask.task_id, panelNumber, modificationRequest, referenceImage);
      
      setModificationRequest('');
      setReferenceImage(null);
      if (referenceInputRef.current) {
        referenceInputRef.current.value = '';
      }

      // The progress will be updated via WebSocket or polling

    } catch (error) {
      setRegeneratingPanel(null);
      setError(handleApiError(error));
    }
  };

  const handleCancelTask = async () => {
    if (!currentTask || !isTaskActive(status)) {
      return;
    }

    try {
      await cancelTask(currentTask.task_id);
      setIsGenerating(false);
      setStatus(TASK_STATUS.CANCELLED);
      setStatusMessage('任务已取消');
      loadTaskHistory();
    } catch (error) {
      setError(handleApiError(error));
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.type !== 'text/plain') {
        setError('只支持 .txt 文件');
        return;
      }
      setUploadedFile(file);
      setError('');
    }
  };

  const handleReferenceImageSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        setError('只支持图片文件');
        return;
      }
      setReferenceImage(file);
      setError('');
    }
  };

  const getStatusIcon = (taskStatus) => {
    if (isTaskActive(taskStatus)) {
      return <Clock className="w-4 h-4 text-blue-500 animate-spin" />;
    } else if (isTaskCompleted(taskStatus)) {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    } else if (isTaskFailed(taskStatus)) {
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
    return null;
  };

  return (
    <div className="async-manga-generator">
      {/* Connection Status */}
      <div className="connection-status mb-4">
        <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
          wsConnected ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
        }`}>
          <div className={`w-2 h-2 rounded-full mr-2 ${
            wsConnected ? 'bg-green-500' : 'bg-yellow-500'
          }`} />
          {wsConnected ? '实时连接已建立' : '使用轮询模式'}
        </div>
      </div>

      {/* Input Section */}
      <div className="input-section mb-6">
        <div className="tabs mb-4">
          <button
            className={`tab-button ${!uploadedFile ? 'active' : ''}`}
            onClick={() => setUploadedFile(null)}
          >
            <FileText className="w-4 h-4 mr-2" />
            文本输入
          </button>
          <button
            className={`tab-button ${uploadedFile ? 'active' : ''}`}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="w-4 h-4 mr-2" />
            文件上传
          </button>
        </div>

        {!uploadedFile ? (
          <div className="text-input">
            <textarea
              value={storyText}
              onChange={(e) => setStoryText(e.target.value)}
              placeholder="请输入您的故事..."
              rows={6}
              disabled={isGenerating}
              className="w-full p-3 border rounded-lg resize-none"
            />
          </div>
        ) : (
          <div className="file-input">
            <div className="uploaded-file-info">
              <FileText className="w-5 h-5 mr-2" />
              <span>{uploadedFile.name}</span>
              <button
                onClick={() => setUploadedFile(null)}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".txt"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Style Options */}
        <div className="style-options mt-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">场景数量</label>
              <input
                type="number"
                min="1"
                max="10"
                value={numScenes}
                onChange={(e) => setNumScenes(parseInt(e.target.value))}
                disabled={isGenerating}
                className="w-full p-2 border rounded"
              />
            </div>
            {/* Add other style options here */}
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium mb-1">附加说明</label>
            <textarea
              value={additionalNotes}
              onChange={(e) => setAdditionalNotes(e.target.value)}
              placeholder="可选：添加特殊要求或风格说明..."
              rows={2}
              disabled={isGenerating}
              className="w-full p-2 border rounded resize-none"
            />
          </div>
        </div>

        {/* Generate Button */}
        <div className="mt-4">
          <button
            onClick={uploadedFile ? handleFileUpload : handleGenerateManga}
            disabled={isGenerating || (!storyText.trim() && !uploadedFile)}
            className="generate-button"
          >
            {isGenerating ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <Wand2 className="w-4 h-4 mr-2" />
                生成漫画
              </>
            )}
          </button>

          {isGenerating && isTaskActive(status) && (
            <button
              onClick={handleCancelTask}
              className="ml-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
            >
              取消任务
            </button>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-message mb-4">
          <AlertCircle className="w-4 h-4 mr-2" />
          {error}
        </div>
      )}

      {/* Progress Section */}
      {isGenerating && (
        <div className="progress-section mb-6">
          <div className="progress-header">
            <div className="flex items-center">
              {getStatusIcon(status)}
              <span className="ml-2 font-medium">任务进度</span>
            </div>
            <span className="text-sm text-gray-600">{progress}%</span>
          </div>
          
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          
          <div className="status-message mt-2">
            {statusMessage}
          </div>
        </div>
      )}

      {/* Panels Section */}
      {panels.length > 0 && (
        <div className="panels-section mb-6">
          <h3 className="text-lg font-semibold mb-4">生成的漫画面板</h3>
          <div className="panels-grid">
            {panels.map((panel, index) => (
              <div key={index} className="panel-item">
                <div className="panel-header">
                  <span className="panel-number">面板 {panel.panel_number}</span>
                  {panel.status && (
                    <span className={`panel-status ${panel.status.toLowerCase()}`}>
                      {panel.status}
                    </span>
                  )}
                </div>
                
                {panel.image_url && (
                  <img
                    src={panel.image_url}
                    alt={`Panel ${panel.panel_number}`}
                    loading="lazy"
                    className="panel-image"
                  />
                )}
                
                <div className="panel-description">
                  {panel.scene_description}
                </div>

                {/* Regeneration Controls */}
                {isTaskCompleted(status) && (
                  <div className="panel-controls mt-2">
                    <button
                      onClick={() => setRegeneratingPanel(panel.panel_number)}
                      disabled={regeneratingPanel === panel.panel_number}
                      className="regenerate-button"
                    >
                      <RefreshCw className={`w-3 h-3 mr-1 ${
                        regeneratingPanel === panel.panel_number ? 'animate-spin' : ''
                      }`} />
                      重新生成
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Regeneration Modal */}
      {regeneratingPanel && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>重新生成面板 {regeneratingPanel}</h3>
              <button
                onClick={() => setRegeneratingPanel(null)}
                className="close-button"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="modal-body">
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">修改要求</label>
                <textarea
                  value={modificationRequest}
                  onChange={(e) => setModificationRequest(e.target.value)}
                  placeholder="请描述您希望如何修改这个面板..."
                  rows={3}
                  className="w-full p-2 border rounded resize-none"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">参考图片（可选）</label>
                <input
                  ref={referenceInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleReferenceImageSelect}
                  className="w-full p-2 border rounded"
                />
                {referenceImage && (
                  <div className="mt-2 text-sm text-gray-600">
                    已选择: {referenceImage.name}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => setRegeneratingPanel(null)}
                className="cancel-button"
              >
                取消
              </button>
              <button
                onClick={() => handleRegeneratePanel(regeneratingPanel)}
                disabled={!modificationRequest.trim()}
                className="confirm-button"
              >
                开始重新生成
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task History */}
      <div className="task-history">
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="history-toggle"
        >
          任务历史 ({taskHistory.length})
        </button>

        {showHistory && (
          <div className="history-list mt-4">
            {taskHistory.map((task) => (
              <div key={task.task_id} className="history-item">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    {getStatusIcon(task.status)}
                    <span className="ml-2 text-sm">
                      {task.story_preview}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date(task.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AsyncMangaGenerator;