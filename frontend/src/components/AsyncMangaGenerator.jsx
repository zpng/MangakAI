/**
 * Async Manga Generator Component
 * Handles asynchronous manga generation with real-time progress updates
 */
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Routes, Route, Navigate } from 'react-router-dom';
import { Upload, Download, RefreshCw, FileText, Image, Wand2, X, CheckCircle, AlertCircle, Clock, BookOpen } from 'lucide-react';
import websocketService from '../services/websocket';
import '../App.css'; // Import the same CSS as App.jsx
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
  TASK_STATUS,
  getStyleOptions,
  getExamples,
  getExample,
  createPDF,
  getCurrentPanels
} from '../services/api';

const AsyncMangaGenerator = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  // Get current tab from URL path
  const getCurrentTab = () => {
    const path = location.pathname;
    if (path === '/' || path === '/home') return 'generate-text';
    if (path === '/upload') return 'generate-file';
    if (path === '/regenerate') return 'regenerate';
    if (path === '/histories') return 'pdf';
    if (path === '/examples') return 'examples';
    return 'generate-text';
  };

  // Tab state - now derived from URL
  const [activeTab, setActiveTab] = useState(getCurrentTab());
  
  // Update activeTab when location changes
  useEffect(() => {
    setActiveTab(getCurrentTab());
  }, [location.pathname]);

  // Function to handle tab changes with navigation
  const handleTabChange = (tabName) => {
    const routes = {
      'generate-text': '/home',
      'generate-file': '/upload',
      'regenerate': '/regenerate',
      'pdf': '/histories',
      'examples': '/examples'
    };
    navigate(routes[tabName] || '/home');
  };

  // Form states
  const [storyText, setStoryText] = useState('');
  const [numScenes, setNumScenes] = useState(5);
  const [styleOptions, setStyleOptions] = useState({});
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
  const [showHistory, setShowHistory] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  // Regeneration states
  const [regeneratingPanel, setRegeneratingPanel] = useState(null);
  const [modificationRequest, setModificationRequest] = useState('');
  const [referenceImage, setReferenceImage] = useState(null);
  const [panelNumber, setPanelNumber] = useState(1);
  const [replaceOriginal, setReplaceOriginal] = useState(false);
  const [regeneratedImage, setRegeneratedImage] = useState(null);
  const [regenerationStatus, setRegenerationStatus] = useState('');

  // PDF states
  const [pdfStatus, setPdfStatus] = useState('');
  const [pdfPath, setPdfPath] = useState(null);

  // Examples states
  const [examples, setExamples] = useState({});
  const [selectedExample, setSelectedExample] = useState('');
  const [exampleData, setExampleData] = useState(null);
  const [selectedPanelIndex, setSelectedPanelIndex] = useState(0);

  // Gallery states
  const [galleryImages, setGalleryImages] = useState([]);
  const [sceneDescriptions, setSceneDescriptions] = useState('');

  // Refs
  const fileInputRef = useRef(null);
  const referenceInputRef = useRef(null);

  useEffect(() => {
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Load task history and check for active tasks
    loadTaskHistoryAndRestoreState();

    // Load style options
    fetchStyleOptions();

    // Load examples
    fetchExamples();

    // Cleanup on unmount
    return () => {
      websocketService.disconnect();
    };
  }, []);

  const loadTaskHistoryAndRestoreState = async () => {
    try {
      const response = await getUserTasks(10, 0);
      const tasks = response.data.tasks || [];
      setTaskHistory(tasks);

      // Check for active tasks and restore state
      const activeTask = tasks.find(task => isTaskActive(task.status));
      if (activeTask) {
        console.log('Found active task on page load:', activeTask);
        await restoreActiveTaskState(activeTask);
      }
    } catch (error) {
      console.error('Failed to load task history:', error);
    }
  };

  const restoreActiveTaskState = async (task) => {
    try {
      // Set current task
      setCurrentTask({
        task_id: task.task_id,
        status: task.status
      });

      // Get detailed task status
      const statusResponse = await getTaskStatus(task.task_id);
      const taskData = statusResponse.data;

      // Restore UI state
      setIsGenerating(true);
      setStatus(taskData.status);
      setProgress(taskData.progress || 0);
      setStatusMessage(getStatusMessage(
        taskData.status, 
        taskData.progress, 
        taskData.current_panel, 
        taskData.total_panels
      ));

      // Restore panels if available
      if (taskData.panels && taskData.panels.length > 0) {
        setPanels(taskData.panels);
        // Convert panels to gallery format
        const galleryUrls = taskData.panels.map(panel => panel.image_url);
        setGalleryImages(galleryUrls);
        
        // Set scene descriptions
        const descriptions = taskData.panels.map(panel => panel.scene_description).join('\n\n');
        setSceneDescriptions(descriptions);
      }

      // Wait a bit for WebSocket to be ready, then subscribe
      setTimeout(() => {
        if (wsConnected) {
          websocketService.subscribeToTask(task.task_id);
        } else {
          // Fallback to polling if WebSocket is not available
          startPolling(task.task_id);
        }
      }, 1000);

      console.log('Successfully restored active task state');
    } catch (error) {
      console.error('Failed to restore active task state:', error);
      // If we can't restore the task state, just clear the active task
      setCurrentTask(null);
      setIsGenerating(false);
    }
  };

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

  const fetchStyleOptions = async () => {
    try {
      const response = await getStyleOptions();
      setStyleOptions(response.data);
    } catch (error) {
      console.error('Error fetching style options:', error);
    }
  };

  const fetchExamples = async () => {
    try {
      const response = await getExamples();
      const exampleNames = response.data.examples;
      setExamples(exampleNames);
      if (exampleNames.length > 0) {
        setSelectedExample(exampleNames[0]);
        fetchExampleData(exampleNames[0]);
      }
    } catch (error) {
      console.error('Error fetching examples:', error);
      // Fallback to mock data when API is not available
      const mockExamples = ['The Little Lantern', 'The Paper Kite', 'The Stray Puppy'];
      setExamples(mockExamples);
      setSelectedExample(mockExamples[0]);
      fetchExampleData(mockExamples[0]);
    }
  };

  const fetchExampleData = async (exampleName) => {
    try {
      const response = await getExample(exampleName);
      console.log('Fetched example data:', response.data);
      console.log('Panels array:', response.data.panels);
      setExampleData(response.data);
    } catch (error) {
      console.error('Error fetching example data:', error);
      // Fallback to mock data when API is not available
      const mockData = {
        title: exampleName,
        story: "This is a sample story for demonstration purposes. In a small coastal village, where the sea whispered secrets to the shore, there lived a curious boy named Arun. Every evening, as the sun dipped behind the hills and the sky turned shades of orange and violet, Arun would carry his little lantern and sit on the rocks, watching the restless waves dance under the fading light.",
        panels: [
          "/static/examples/LittleLantern/scene1.png",
          "/static/examples/LittleLantern/scene2.png", 
          "/static/examples/LittleLantern/scene3.png",
          "/static/examples/LittleLantern/scene4.png",
          "/static/examples/LittleLantern/scene5.png"
        ]
      };
      setExampleData(mockData);
    }
  };

  const handleExampleChange = (exampleName) => {
    setSelectedExample(exampleName);
    setSelectedPanelIndex(0);
    fetchExampleData(exampleName);
  };

  const handleProgressUpdate = (data) => {
    const { task_id, status, progress, message, panels: updatedPanels, current_panel, total_panels } = data;

    if (currentTask && task_id === currentTask.task_id) {
      setStatus(status);
      setProgress(progress || 0);
      setStatusMessage(message || getStatusMessage(status, progress, current_panel, total_panels));

      if (updatedPanels && updatedPanels.length > 0) {
        setPanels(updatedPanels);
        // Convert panels to gallery format
        const galleryUrls = updatedPanels.map(panel => panel.image_url);
        setGalleryImages(galleryUrls);
        
        // Set scene descriptions
        const descriptions = updatedPanels.map(panel => panel.scene_description).join('\n\n');
        setSceneDescriptions(descriptions);
      }

      if (isTaskCompleted(status) || isTaskFailed(status)) {
        setIsGenerating(false);
        loadTaskHistory();
      }
    }
  };

  const loadTaskHistory = async () => {
    try {
      const response = await getUserTasks(10, 0);
      setTaskHistory(response.data.tasks || []);
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
      setGalleryImages([]);
      setSceneDescriptions('');

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

  const handleFileUpload = async (file) => {
    if (!file) {
      setError('请选择文件');
      return;
    }

    try {
      setIsGenerating(true);
      setError('');
      setProgress(0);
      setPanels([]);
      setGalleryImages([]);
      setSceneDescriptions('');

      const options = {
        num_scenes: numScenes,
        ...selectedStyles,
        additional_notes: additionalNotes
      };

      const response = await createMangaTaskFromFile(file, options);
      const task = response.data;

      setCurrentTask(task);
      setStatus(task.status);
      setStatusMessage('任务已创建，正在处理中...');

      // Subscribe to task updates via WebSocket
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
        setProgress(taskData.progress || 0);
        setStatusMessage(getStatusMessage(
          taskData.status, 
          taskData.progress, 
          taskData.current_panel, 
          taskData.total_panels
        ));

        if (taskData.panels && taskData.panels.length > 0) {
          setPanels(taskData.panels);
          // Convert panels to gallery format
          const galleryUrls = taskData.panels.map(panel => panel.image_url);
          setGalleryImages(galleryUrls);
          
          // Set scene descriptions
          const descriptions = taskData.panels.map(panel => panel.scene_description).join('\n\n');
          setSceneDescriptions(descriptions);
        }

        if (isTaskCompleted(taskData.status) || isTaskFailed(taskData.status)) {
          setIsGenerating(false);
          clearInterval(pollInterval);
          loadTaskHistory();
        }

      } catch (error) {
        console.error('Polling error:', error);
        clearInterval(pollInterval);
        setIsGenerating(false);
        setError('获取任务状态失败');
      }
    }, 2000); // Poll every 2 seconds

    // Clean up polling after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      if (isGenerating) {
        setIsGenerating(false);
        setError('任务超时，请检查任务状态');
      }
    }, 600000);
  };

  const handleRegeneratePanel = async () => {
    if (!modificationRequest.trim()) {
      setError('请输入修改要求');
      return;
    }

    try {
      setRegenerationStatus('正在重新生成面板...');
      setError('');

      const response = await regeneratePanel(
        currentTask?.task_id || 'current',
        panelNumber,
        modificationRequest,
        referenceImage
      );

      setRegeneratedImage(response.data.image_path);
      setRegenerationStatus('面板重新生成完成！');
      setModificationRequest('');
      setReferenceImage(null);

      // Update gallery if replace original is selected
      if (replaceOriginal && galleryImages.length > 0) {
        const newGalleryImages = [...galleryImages];
        newGalleryImages[panelNumber - 1] = response.data.image_path;
        setGalleryImages(newGalleryImages);
      }

    } catch (error) {
      setRegenerationStatus('');
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

  const handleCreatePDF = async () => {
    try {
      setPdfStatus('正在创建PDF...');
      const response = await createPDF();
      setPdfPath(response.data.pdf_path);
      setPdfStatus('PDF创建成功！');
    } catch (error) {
      setPdfStatus('PDF创建失败');
      setError(handleApiError(error));
    }
  };

  const downloadPanel = async (panelUrl, index) => {
    try {
      const API_BASE_URL = 'http://localhost:8000';
      const fullUrl = `${API_BASE_URL}${panelUrl}`;
      window.open(fullUrl, '_blank');
    } catch (error) {
      console.error('Download failed:', error);
      alert('下载失败，请右键点击图片另存为');
    }
  };

  const handleViewTask = async (taskId) => {
    try {
      setError('');
      
      // Get detailed task status
      const response = await getTaskStatus(taskId);
      const taskData = response.data;
      
      // Update current task
      setCurrentTask({ task_id: taskId, status: taskData.status });
      setStatus(taskData.status);
      setProgress(taskData.progress);
      setStatusMessage(getStatusMessage(taskData.status, taskData.progress, taskData.current_panel, taskData.total_panels));
      
      // Update panels if completed
      if (taskData.panels && taskData.panels.length > 0) {
        setPanels(taskData.panels);
        
        // Extract images for gallery
        const images = taskData.panels
          .filter(panel => panel.image_url)
          .map(panel => panel.image_url);
        setGalleryImages(images);
        
        // Extract scene descriptions
        const descriptions = taskData.panels
          .map((panel, index) => `Scene ${index + 1}: ${panel.scene_description}`)
          .join('\n\n');
        setSceneDescriptions(descriptions);
      }
      
      // Show task details
      setShowHistory(true);
      
    } catch (error) {
      setError(`查看任务失败: ${handleApiError(error)}`);
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
      // Auto-generate from file
      handleFileUpload(file);
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

  // Helper components
  const StyleDropdown = ({ label, value, onChange, options }) => (
    <div className="style-dropdown">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="None">None</option>
        {options && options.map(option => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </div>
  );

  const ImageGallery = ({ images, title }) => (
    <div className="image-gallery">
      <h3>{title}</h3>
      <div className="gallery-grid">
        {images && images.map((image, index) => (
          <div key={index} className="gallery-item">
            <img src={`http://localhost:8000${image}`} alt={`Panel ${index + 1}`} />
            <div className="panel-number">Panel {index + 1}</div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>📚 MangakAI</h1>
        <p>Transform your stories into manga panels with AI and custom style preferences!</p>
      </header>

      <div className="tab-container">
        {/* Connection Status */}
        <div className="connection-status" style={{ padding: '15px', borderBottom: '1px solid #eee' }}>
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
            wsConnected ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
          }`}>
            <div className={`w-2 h-2 rounded-full mr-2 ${
              wsConnected ? 'bg-green-500' : 'bg-yellow-500'
            }`} />
            {wsConnected ? '实时连接已建立' : '使用轮询模式'}
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="tab-buttons">
          <button 
            className={activeTab === 'generate-text' ? 'active' : ''}
            onClick={() => handleTabChange('generate-text')}
          >
            <FileText size={20} />
            Text Input
          </button>
          <button 
            className={activeTab === 'generate-file' ? 'active' : ''}
            onClick={() => handleTabChange('generate-file')}
          >
            <Upload size={20} />
            File Upload
          </button>
          <button 
            className={activeTab === 'regenerate' ? 'active' : ''}
            onClick={() => handleTabChange('regenerate')}
          >
            <RefreshCw size={20} />
            Regenerate Panels
          </button>
          <button 
            className={activeTab === 'pdf' ? 'active' : ''}
            onClick={() => handleTabChange('pdf')}
          >
            <Download size={20} />
            历史任务
          </button>
          <button 
            className={activeTab === 'examples' ? 'active' : ''}
            onClick={() => handleTabChange('examples')}
          >
            <BookOpen size={20} />
            Examples
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'generate-text' && (
            <div className="generate-text-tab">
              {/* Input Section */}
              <div className="input-section">
                <div className="story-input">
                  <label>Enter your story</label>
                  <textarea
                    value={storyText}
                    onChange={(e) => setStoryText(e.target.value)}
                    placeholder="Once upon a time..."
                    rows={10}
                    disabled={isGenerating}
                  />
                </div>

                <div className="scenes-input">
                  <label>Number of Scenes</label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={numScenes}
                    onChange={(e) => setNumScenes(parseInt(e.target.value))}
                    disabled={isGenerating}
                  />
                  <span>{numScenes}</span>
                </div>
              </div>

              <div className="style-section">
                <h3>🎨 Style Preferences</h3>
                <div className="style-grid">
                  <StyleDropdown
                    label="Art Style"
                    value={selectedStyles.art_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, art_style: value})}
                    options={styleOptions.art_styles}
                  />
                  <StyleDropdown
                    label="Overall Mood"
                    value={selectedStyles.mood}
                    onChange={(value) => setSelectedStyles({...selectedStyles, mood: value})}
                    options={styleOptions.mood_options}
                  />
                  <StyleDropdown
                    label="Color Palette"
                    value={selectedStyles.color_palette}
                    onChange={(value) => setSelectedStyles({...selectedStyles, color_palette: value})}
                    options={styleOptions.color_palettes}
                  />
                  <StyleDropdown
                    label="Character Style"
                    value={selectedStyles.character_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, character_style: value})}
                    options={styleOptions.character_styles}
                  />
                  <StyleDropdown
                    label="Line Art Style"
                    value={selectedStyles.line_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, line_style: value})}
                    options={styleOptions.line_styles}
                  />
                  <StyleDropdown
                    label="Composition Style"
                    value={selectedStyles.composition}
                    onChange={(value) => setSelectedStyles({...selectedStyles, composition: value})}
                    options={styleOptions.composition_styles}
                  />
                </div>
                
                <div className="additional-notes">
                  <label>Additional Style Notes</label>
                  <textarea
                    value={additionalNotes}
                    onChange={(e) => setAdditionalNotes(e.target.value)}
                    placeholder="Any specific style preferences, character descriptions, or artistic directions..."
                    rows={3}
                    disabled={isGenerating}
                  />
                </div>
              </div>

              <button 
                className="generate-btn"
                onClick={handleGenerateManga}
                disabled={isGenerating || !storyText.trim()}
              >
                {isGenerating ? (
                  <>
                    <RefreshCw className="spinning" size={20} />
                    Generating...
                  </>
                ) : (
                  <>
                    <Wand2 size={20} />
                    Generate Manga
                  </>
                )}
              </button>

              {isGenerating && isTaskActive(status) && (
                <button
                  onClick={handleCancelTask}
                  style={{ 
                    marginLeft: '10px', 
                    padding: '12px 24px', 
                    backgroundColor: '#dc3545', 
                    color: 'white', 
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer'
                  }}
                >
                  取消任务
                </button>
              )}

              {/* Error Display */}
              {error && (
                <div className="error-message" style={{ 
                  marginTop: '20px',
                  padding: '12px',
                  backgroundColor: '#f8d7da',
                  color: '#721c24',
                  border: '1px solid #f5c6cb',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  <AlertCircle size={16} style={{ marginRight: '8px' }} />
                  {error}
                </div>
              )}

              {/* Progress Section */}
              {isGenerating && (
                <div className="progress-section" style={{ marginTop: '20px' }}>
                  <div className="progress-header" style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: '10px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {getStatusIcon(status)}
                      <span style={{ marginLeft: '8px', fontWeight: '500' }}>任务进度</span>
                    </div>
                    <span style={{ fontSize: '14px', color: '#666' }}>{progress}%</span>
                  </div>
                  
                  <div className="progress-bar" style={{
                    width: '100%',
                    height: '8px',
                    backgroundColor: '#e9ecef',
                    borderRadius: '4px',
                    overflow: 'hidden'
                  }}>
                    <div
                      className="progress-fill"
                      style={{ 
                        width: `${progress}%`,
                        height: '100%',
                        backgroundColor: '#007bff',
                        transition: 'width 0.3s ease'
                      }}
                    />
                  </div>
                  
                  <div className="status-message" style={{ 
                    marginTop: '8px',
                    fontSize: '14px',
                    color: '#666'
                  }}>
                    {statusMessage}
                  </div>
                </div>
              )}

              {/* Task History Section */}
              <div className="task-history-section" style={{ marginTop: '30px' }}>
                <div className="task-history-header" style={{ 
                  marginBottom: '15px'
                }}>
                  <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>任务历史</h3>
                </div>

                <div className="task-history-list" style={{
                  border: '1px solid #e0e0e0',
                  borderRadius: '8px',
                  backgroundColor: '#fafafa',
                  maxHeight: '400px',
                  overflowY: 'auto'
                }}>
                  {taskHistory.length === 0 ? (
                    <div style={{ 
                      padding: '20px', 
                      textAlign: 'center', 
                      color: '#666',
                      fontSize: '14px'
                    }}>
                      暂无任务历史
                    </div>
                  ) : (
                    taskHistory.map((task, index) => (
                      <TaskHistoryItem 
                        key={task.task_id} 
                        task={task} 
                        index={index}
                        onViewTask={(taskId) => handleViewTask(taskId)}
                        onCreatePDF={(taskId) => handleCreatePDF(taskId)}
                      />
                    ))
                  )}
                </div>
              </div>

              {galleryImages.length > 0 && (
                <ImageGallery images={galleryImages} title="Generated Manga Panels" />
              )}

              {sceneDescriptions && (
                <div className="scene-descriptions">
                  <h3>Scene Descriptions</h3>
                  <textarea value={sceneDescriptions} readOnly rows={10} />
                </div>
              )}
            </div>
          )}

          {activeTab === 'generate-file' && (
            <div className="generate-file-tab">
              <div className="file-upload">
                <label>Upload Story File (.txt)</label>
                <input
                  type="file"
                  accept=".txt"
                  onChange={handleFileSelect}
                />
              </div>

              <div className="scenes-input">
                <label>Number of Scenes</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={numScenes}
                  onChange={(e) => setNumScenes(parseInt(e.target.value))}
                />
                <span>{numScenes}</span>
              </div>

              <div className="style-section">
                <h3>🎨 Style Preferences</h3>
                <div className="style-grid">
                  <StyleDropdown
                    label="Art Style"
                    value={selectedStyles.art_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, art_style: value})}
                    options={styleOptions.art_styles}
                  />
                  <StyleDropdown
                    label="Overall Mood"
                    value={selectedStyles.mood}
                    onChange={(value) => setSelectedStyles({...selectedStyles, mood: value})}
                    options={styleOptions.mood_options}
                  />
                  <StyleDropdown
                    label="Color Palette"
                    value={selectedStyles.color_palette}
                    onChange={(value) => setSelectedStyles({...selectedStyles, color_palette: value})}
                    options={styleOptions.color_palettes}
                  />
                  <StyleDropdown
                    label="Character Style"
                    value={selectedStyles.character_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, character_style: value})}
                    options={styleOptions.character_styles}
                  />
                  <StyleDropdown
                    label="Line Art Style"
                    value={selectedStyles.line_style}
                    onChange={(value) => setSelectedStyles({...selectedStyles, line_style: value})}
                    options={styleOptions.line_styles}
                  />
                  <StyleDropdown
                    label="Composition Style"
                    value={selectedStyles.composition}
                    onChange={(value) => setSelectedStyles({...selectedStyles, composition: value})}
                    options={styleOptions.composition_styles}
                  />
                </div>
                
                <div className="additional-notes">
                  <label>Additional Style Notes</label>
                  <textarea
                    value={additionalNotes}
                    onChange={(e) => setAdditionalNotes(e.target.value)}
                    placeholder="Any specific style preferences, character descriptions, or artistic directions..."
                    rows={3}
                  />
                </div>
              </div>

              {galleryImages.length > 0 && (
                <ImageGallery images={galleryImages} title="Generated Manga Panels" />
              )}

              {sceneDescriptions && (
                <div className="scene-descriptions">
                  <h3>Scene Descriptions</h3>
                  <textarea value={sceneDescriptions} readOnly rows={10} />
                </div>
              )}
            </div>
          )}

          {activeTab === 'regenerate' && (
            <div className="regenerate-tab">
              <h3>Select a panel to regenerate with modifications</h3>
              <p><strong>Note:</strong> You must generate manga first before you can regenerate panels.</p>
              
              <div className="regenerate-controls">
                <div className="panel-selector">
                  <label>Panel Number to Regenerate</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={panelNumber}
                    onChange={(e) => setPanelNumber(parseInt(e.target.value))}
                  />
                </div>

                <div className="modification-input">
                  <label>Modification Request</label>
                  <textarea
                    value={modificationRequest}
                    onChange={(e) => setModificationRequest(e.target.value)}
                    placeholder="Describe how you want to modify this panel..."
                    rows={4}
                  />
                </div>

                <div className="reference-upload">
                  <label>Reference Image (Optional)</label>
                  <input
                    ref={referenceInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleReferenceImageSelect}
                  />
                  {referenceImage && (
                    <div className="reference-preview">
                      Selected: {referenceImage.name}
                    </div>
                  )}
                </div>

                <div className="replace-option">
                  <label>
                    <input
                      type="checkbox"
                      checked={replaceOriginal}
                      onChange={(e) => setReplaceOriginal(e.target.checked)}
                    />
                    Replace original panel in gallery
                  </label>
                </div>

                <button 
                  className="regenerate-btn"
                  onClick={handleRegeneratePanel}
                  disabled={!modificationRequest.trim()}
                >
                  <RefreshCw size={20} />
                  Regenerate Panel
                </button>
              </div>

              {regenerationStatus && (
                <div className="status-message">
                  <p>{regenerationStatus}</p>
                </div>
              )}

              {regeneratedImage && (
                <div className="regenerated-image">
                  <h3>Regenerated Panel</h3>
                  <img src={`http://localhost:8000${regeneratedImage}`} alt="Regenerated Panel" />
                </div>
              )}

              {galleryImages.length > 0 && (
                <ImageGallery images={galleryImages} title="Updated Main Gallery" />
              )}
            </div>
          )}

          {activeTab === 'pdf' && (
            <div className="pdf-tab">
              <h3>历史任务管理</h3>
              <p><strong>说明:</strong> 在这里查看和管理所有的漫画生成任务，并可以为已完成的任务创建PDF。</p>
              


              {/* Task History Section */}
              <div className="task-history-section" style={{ marginTop: '30px' }}>
                <div className="task-history-header" style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: '15px'
                }}>
                  <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>任务历史</h3>
                  <button
                    onClick={() => setShowHistory(!showHistory)}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: 'transparent',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    {showHistory ? '隐藏' : '显示'} ({taskHistory.length})
                  </button>
                </div>

                {showHistory && (
                  <div className="task-history-list" style={{
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    backgroundColor: '#fafafa',
                    maxHeight: '400px',
                    overflowY: 'auto'
                  }}>
                    {taskHistory.length === 0 ? (
                      <div style={{ 
                        padding: '20px', 
                        textAlign: 'center', 
                        color: '#666',
                        fontSize: '14px'
                      }}>
                        暂无任务历史
                      </div>
                    ) : (
                      taskHistory.map((task, index) => (
                        <TaskHistoryItem 
                          key={task.task_id} 
                          task={task} 
                          index={index}
                          onViewTask={(taskId) => handleViewTask(taskId)}
                          onCreatePDF={(taskId) => handleCreatePDF(taskId)}
                        />
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* Current Task Progress Section */}
              {isGenerating && (
                <div className="progress-section" style={{ marginTop: '20px' }}>
                  <div className="progress-header" style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: '10px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {getStatusIcon(status)}
                      <span style={{ marginLeft: '8px', fontWeight: '500' }}>当前任务进度</span>
                    </div>
                    <span style={{ fontSize: '14px', color: '#666' }}>{progress}%</span>
                  </div>
                  
                  <div className="progress-bar" style={{
                    width: '100%',
                    height: '8px',
                    backgroundColor: '#e9ecef',
                    borderRadius: '4px',
                    overflow: 'hidden'
                  }}>
                    <div
                      className="progress-fill"
                      style={{ 
                        width: `${progress}%`,
                        height: '100%',
                        backgroundColor: '#007bff',
                        transition: 'width 0.3s ease'
                      }}
                    />
                  </div>
                  
                  <div className="status-message" style={{ 
                    marginTop: '8px',
                    fontSize: '14px',
                    color: '#666'
                  }}>
                    {statusMessage}
                  </div>

                  {isGenerating && isTaskActive(status) && (
                    <button
                      onClick={handleCancelTask}
                      style={{ 
                        marginTop: '10px',
                        padding: '8px 16px', 
                        backgroundColor: '#dc3545', 
                        color: 'white', 
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px'
                      }}
                    >
                      取消任务
                    </button>
                  )}
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="error-message" style={{ 
                  marginTop: '20px',
                  padding: '12px',
                  backgroundColor: '#f8d7da',
                  color: '#721c24',
                  border: '1px solid #f5c6cb',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  <AlertCircle size={16} style={{ marginRight: '8px' }} />
                  {error}
                </div>
              )}

              {/* Generated Panels Gallery */}
              {galleryImages.length > 0 && (
                <ImageGallery images={galleryImages} title="Generated Manga Panels" />
              )}

              {/* Scene Descriptions */}
              {sceneDescriptions && (
                <div className="scene-descriptions">
                  <h3>Scene Descriptions</h3>
                  <textarea value={sceneDescriptions} readOnly rows={10} />
                </div>
              )}
            </div>
          )}

          {activeTab === 'examples' && (
            <div className="examples-tab">
              <h3>Explore Example Stories and Manga</h3>
              <p>Select from our curated examples to see how stories transform into manga panels!</p>
              
              {exampleData && (
                <div className="examples-layout">
                  <div className="examples-left-panel">
                    <div className="example-selector">
                      <label>Select Example</label>
                      <select 
                        value={selectedExample} 
                        onChange={(e) => handleExampleChange(e.target.value)}
                      >
                        {examples.map && examples.map(example => (
                          <option key={example} value={example}>{example}</option>
                        ))}
                      </select>
                    </div>

                    <div className="example-story">
                      <div className="story-title-section">
                        <label>Story Title</label>
                        <input type="text" value={exampleData.title} readOnly />
                      </div>
                      
                      <div className="story-text-section">
                        <label>Story Text</label>
                        <textarea value={exampleData.story} readOnly rows={15} />
                      </div>
                    </div>

                    <div className="how-it-works">
                      <h4>How It Works:</h4>
                      <ol>
                        <li><strong>Select an Example:</strong> Choose from the dropdown above</li>
                        <li><strong>View the Story:</strong> Read the original story text</li>
                        <li><strong>See the Manga:</strong> Observe how AI transforms text into visual panels</li>
                      </ol>
                    </div>
                  </div>
                  
                  <div className="examples-right-panel">
                    <div className="manga-display">
                      <div className="manga-header">
                        <h4>See the Manga</h4>
                        <div className="manga-controls">
                          <button 
                            className="control-btn" 
                            onClick={() => downloadPanel(exampleData.panels[selectedPanelIndex], selectedPanelIndex)}
                            title="下载当前面板"
                          >
                            ↓
                          </button>
                        </div>
                      </div>
                      <div className="manga-content">
                        {exampleData.panels && exampleData.panels.length > 0 ? (
                          <>
                            <div className="main-manga-panel">
                              <img src={`http://localhost:8000${exampleData.panels[selectedPanelIndex]}`} alt={`Manga panel ${selectedPanelIndex + 1}`} />
                            </div>
                            <div className="manga-thumbnails">
                              {console.log('Rendering thumbnails, panels:', exampleData.panels)}
                              {exampleData.panels.map((panel, index) => (
                                <div 
                                  key={index} 
                                  className={`thumbnail-item ${index === selectedPanelIndex ? 'active' : ''}`}
                                  onClick={() => setSelectedPanelIndex(index)}
                                >
                                  <img src={`http://localhost:8000${panel}`} alt={`Panel ${index + 1}`} />
                                </div>
                              ))}
                            </div>
                          </>
                        ) : (
                          <div className="no-panels">
                            {console.log('No panels available, exampleData:', exampleData)}
                            No manga panels available
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!exampleData && (
                <div className="loading-examples">
                  <p>Loading example data...</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Task History Item Component
const TaskHistoryItem = ({ task, index, onViewTask, onCreatePDF }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [taskDetails, setTaskDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pdfStatus, setPdfStatus] = useState('');
  const [pdfPath, setPdfPath] = useState(null);

  const getStatusIcon = (status) => {
    switch (status) {
      case TASK_STATUS.COMPLETED:
        return <CheckCircle size={16} style={{ color: '#28a745' }} />;
      case TASK_STATUS.FAILED:
        return <AlertCircle size={16} style={{ color: '#dc3545' }} />;
      case TASK_STATUS.CANCELLED:
        return <X size={16} style={{ color: '#6c757d' }} />;
      default:
        return <Clock size={16} style={{ color: '#007bff' }} />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case TASK_STATUS.COMPLETED:
        return '已完成';
      case TASK_STATUS.FAILED:
        return '失败';
      case TASK_STATUS.CANCELLED:
        return '已取消';
      case TASK_STATUS.PENDING:
        return '等待中';
      case TASK_STATUS.PROCESSING:
        return '处理中';
      case TASK_STATUS.SCENE_GENERATION:
        return '生成场景';
      case TASK_STATUS.IMAGE_GENERATION:
        return '生成图片';
      case TASK_STATUS.PANEL_PROCESSING:
        return '处理面板';
      case TASK_STATUS.UPLOADING:
        return '上传中';
      default:
        return status;
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleToggleExpand = async (e) => {
    e.stopPropagation(); // 防止触发父级的onClick事件
    
    if (task.status !== TASK_STATUS.COMPLETED) {
      return; // 只有已完成的任务才能展开
    }

    if (!isExpanded && !taskDetails) {
      // 首次展开时加载任务详情
      setIsLoading(true);
      try {
        const response = await getTaskStatus(task.task_id);
        setTaskDetails(response.data);
      } catch (error) {
        console.error('Failed to load task details:', error);
      } finally {
        setIsLoading(false);
      }
    }
    
    setIsExpanded(!isExpanded);
  };

  const handleViewTaskClick = (e) => {
    e.stopPropagation();
    onViewTask(task.task_id);
  };

  const handleCreatePDFClick = async (e) => {
    e.stopPropagation();
    try {
      setPdfStatus('正在创建PDF...');
      const response = await createPDF(task.task_id);
      setPdfPath(response.data.pdf_path);
      setPdfStatus('PDF创建成功！');
    } catch (error) {
      setPdfStatus('PDF创建失败');
      console.error('Create PDF failed:', error);
    }
  };

  return (
    <div 
      className="task-history-item"
      style={{
        borderBottom: '1px solid #e0e0e0',
        transition: 'background-color 0.2s'
      }}
    >
      {/* 主要任务信息区域 */}
      <div 
        style={{
          padding: '15px',
          cursor: task.status === TASK_STATUS.COMPLETED ? 'pointer' : 'default',
          ':hover': { backgroundColor: '#f0f0f0' }
        }}
        onClick={task.status === TASK_STATUS.COMPLETED ? handleToggleExpand : undefined}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
              {getStatusIcon(task.status)}
              <span style={{ 
                marginLeft: '8px', 
                fontWeight: '500',
                fontSize: '14px'
              }}>
                任务 #{index + 1} - {getStatusText(task.status)}
              </span>
              <span style={{ 
                marginLeft: '10px',
                fontSize: '12px',
                color: '#666',
                backgroundColor: '#e9ecef',
                padding: '2px 6px',
                borderRadius: '4px'
              }}>
                {task.progress}%
              </span>
              {task.status === TASK_STATUS.COMPLETED && (
                <span style={{ 
                  marginLeft: '10px',
                  fontSize: '12px',
                  color: '#007bff',
                  cursor: 'pointer'
                }}>
                  {isExpanded ? '收起 ▲' : '展开 ▼'}
                </span>
              )}
            </div>
            
            <div style={{ 
              fontSize: '13px', 
              color: '#666', 
              marginBottom: '6px',
              lineHeight: '1.4'
            }}>
              {task.story_preview}
            </div>
            
            <div style={{ 
              fontSize: '12px', 
              color: '#888',
              display: 'flex',
              justifyContent: 'space-between'
            }}>
              <span>创建: {formatDate(task.created_at)}</span>
              {task.completed_at && (
                <span>完成: {formatDate(task.completed_at)}</span>
              )}
            </div>
          </div>
          
          <div style={{ marginLeft: '15px', fontSize: '12px', color: '#666', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <span>{task.total_panels} 面板</span>
            {task.status !== TASK_STATUS.COMPLETED && (
              <button 
                onClick={handleViewTaskClick}
                style={{
                  marginTop: '5px',
                  padding: '4px 8px',
                  fontSize: '11px',
                  backgroundColor: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                查看
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 展开的详细内容区域 */}
      {isExpanded && task.status === TASK_STATUS.COMPLETED && (
        <div style={{
          padding: '0 15px 15px 15px',
          backgroundColor: '#f8f9fa',
          borderTop: '1px solid #e9ecef'
        }}>
          {isLoading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
              加载中...
            </div>
          ) : taskDetails ? (
            <>
              {/* 动漫面板展示 */}
              {taskDetails.panels && taskDetails.panels.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h4 style={{ 
                    margin: '15px 0 10px 0', 
                    fontSize: '14px', 
                    fontWeight: '600',
                    color: '#333'
                  }}>
                    Generated Manga Panels
                  </h4>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
                    gap: '10px',
                    padding: '10px',
                    backgroundColor: 'white',
                    borderRadius: '8px',
                    border: '1px solid #e0e0e0'
                  }}>
                    {taskDetails.panels.map((panel, panelIndex) => (
                      <div key={panelIndex} style={{
                        textAlign: 'center',
                        padding: '8px',
                        border: '1px solid #ddd',
                        borderRadius: '6px',
                        backgroundColor: '#fafafa'
                      }}>
                        <img 
                          src={`http://localhost:8000${panel.image_url}`} 
                          alt={`Panel ${panelIndex + 1}`}
                          style={{
                            width: '100%',
                            height: '120px',
                            objectFit: 'cover',
                            borderRadius: '4px',
                            marginBottom: '5px'
                          }}
                        />
                        <div style={{ 
                          fontSize: '11px', 
                          color: '#666',
                          fontWeight: '500'
                        }}>
                          Panel {panelIndex + 1}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 场景描述 */}
              {taskDetails.scene_descriptions && (
                <div>
                  <h4 style={{ 
                    margin: '15px 0 10px 0', 
                    fontSize: '14px', 
                    fontWeight: '600',
                    color: '#333'
                  }}>
                    Scene Descriptions
                  </h4>
                  <div style={{
                    padding: '12px',
                    backgroundColor: 'white',
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    color: '#555',
                    maxHeight: '200px',
                    overflowY: 'auto'
                  }}>
                    {taskDetails.scene_descriptions}
                  </div>
                </div>
              )}

              {/* 查看完整任务按钮 */}
              <div style={{ marginTop: '15px', textAlign: 'center' }}>
                <button 
                  onClick={handleViewTaskClick}
                  style={{
                    padding: '8px 16px',
                    fontSize: '13px',
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontWeight: '500'
                  }}
                >
                  查看完整任务
                </button>
                <button 
                  onClick={handleCreatePDFClick}
                  disabled={pdfStatus === '正在创建PDF...'}
                  style={{
                    padding: '8px 16px',
                    fontSize: '13px',
                    backgroundColor: pdfStatus === '正在创建PDF...' ? '#6c757d' : '#28a745',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: pdfStatus === '正在创建PDF...' ? 'not-allowed' : 'pointer',
                    fontWeight: '500'
                  }}
                >
                  {pdfStatus === '正在创建PDF...' ? (
                    <>
                      <RefreshCw size={12} style={{ marginRight: '4px', animation: 'spin 1s linear infinite' }} />
                      创建中...
                    </>
                  ) : (
                    <>
                      <Download size={12} style={{ marginRight: '4px' }} />
                      Create PDF
                    </>
                  )}
                </button>
              </div>

              {/* PDF状态和下载链接 */}
              {pdfStatus && pdfStatus !== '正在创建PDF...' && (
                <div style={{ marginTop: '10px', textAlign: 'center' }}>
                  <div style={{ 
                    fontSize: '13px', 
                    color: pdfStatus.includes('成功') ? '#28a745' : '#dc3545',
                    marginBottom: '8px'
                  }}>
                    {pdfStatus}
                  </div>
                  {pdfPath && (
                    <a href={`http://localhost:8000${pdfPath}`} download>
                      <button style={{
                        padding: '6px 12px',
                        fontSize: '12px',
                        backgroundColor: '#17a2b8',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                      }}>
                        <Download size={12} style={{ marginRight: '4px' }} />
                        下载PDF
                      </button>
                    </a>
                  )}
                </div>
              )}
            </>
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
              无法加载任务详情
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AsyncMangaGenerator;