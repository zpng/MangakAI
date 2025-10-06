import React, { useState, useEffect } from 'react';
import { Upload, Download, RefreshCw, FileText, Image, Wand2, Settings, BookOpen } from 'lucide-react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

// Helper function to get or create session ID
const getOrCreateSessionId = () => {
  let sessionId = localStorage.getItem('session_id');
  if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('session_id', sessionId);
  }
  return sessionId;
};

// For testing purposes, let's use a fixed session ID
const getTestSessionId = () => {
  return 'test_session_123';
};

function App() {
  const [activeTab, setActiveTab] = useState('generate-text');
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
  const [galleryImages, setGalleryImages] = useState([]);
  const [sceneDescriptions, setSceneDescriptions] = useState('');
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState({});
  const [selectedExample, setSelectedExample] = useState('');
  const [exampleData, setExampleData] = useState(null);
  const [selectedPanelIndex, setSelectedPanelIndex] = useState(0);
  
  // Regeneration states
  const [panelNumber, setPanelNumber] = useState(1);
  const [modificationRequest, setModificationRequest] = useState('');
  const [replaceOriginal, setReplaceOriginal] = useState(false);
  const [regeneratedImage, setRegeneratedImage] = useState(null);
  const [regenerationStatus, setRegenerationStatus] = useState('');
  
  // PDF states
  const [pdfStatus, setPdfStatus] = useState('');
  const [pdfPath, setPdfPath] = useState(null);
  
  // Task history state
  const [taskHistory, setTaskHistory] = useState([]);

  useEffect(() => {
    // Load style options
    fetchStyleOptions();
    // Load examples
    fetchExamples();
    // Load task history
    loadTaskHistory();
  }, []);

  const fetchStyleOptions = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/style-options`);
      setStyleOptions(response.data);
    } catch (error) {
      console.error('Error fetching style options:', error);
    }
  };

  const fetchExamples = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/examples`);
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
      const response = await axios.get(`${API_BASE_URL}/api/examples/${exampleName}`);
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
    setSelectedPanelIndex(0); // Reset to first panel when example changes
    fetchExampleData(exampleName);
  };

  // Add download function for manga panels
  const downloadPanel = async (panelUrl, panelIndex) => {
    try {
      // Check if panelUrl exists
      if (!panelUrl) {
        throw new Error('Panel URL is not available');
      }

      console.log('Attempting to download:', `${API_BASE_URL}${panelUrl}`);

      // Try direct download approach first
      const fullUrl = `${API_BASE_URL}${panelUrl}`;
      
      // Create download link directly without axios to avoid CORS issues
      const link = document.createElement('a');
      link.href = fullUrl;
      link.target = '_blank';
      
      // Extract filename from URL or create a default one
      const filename = panelUrl.split('/').pop() || `manga_panel_${panelIndex + 1}.png`;
      link.download = filename;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      
      console.log(`Successfully initiated download: ${filename}`);
    } catch (error) {
      console.error('Error downloading panel:', error);
      
      // Fallback: open in new tab if direct download fails
      try {
        const fullUrl = `${API_BASE_URL}${panelUrl}`;
        window.open(fullUrl, '_blank');
        console.log('Opened image in new tab as fallback');
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
        alert('下载失败，请右键点击图片另存为');
      }
    }
  };

  const generateManga = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/generate-manga`, {
        story_text: storyText,
        num_scenes: numScenes,
        art_style: selectedStyles.art_style !== 'None' ? selectedStyles.art_style : null,
        mood: selectedStyles.mood !== 'None' ? selectedStyles.mood : null,
        color_palette: selectedStyles.color_palette !== 'None' ? selectedStyles.color_palette : null,
        character_style: selectedStyles.character_style !== 'None' ? selectedStyles.character_style : null,
        line_style: selectedStyles.line_style !== 'None' ? selectedStyles.line_style : null,
        composition: selectedStyles.composition !== 'None' ? selectedStyles.composition : null,
        additional_notes: additionalNotes
      });

      if (response.data.success) {
        setGalleryImages(response.data.gallery_images);
        setSceneDescriptions(response.data.scene_descriptions);
      } else {
        alert('Error: ' + response.data.message);
      }
    } catch (error) {
      console.error('Error generating manga:', error);
      alert('Error generating manga: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const generateMangaFromFile = async (file) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('num_scenes', numScenes);
      if (selectedStyles.art_style !== 'None') formData.append('art_style', selectedStyles.art_style);
      if (selectedStyles.mood !== 'None') formData.append('mood', selectedStyles.mood);
      if (selectedStyles.color_palette !== 'None') formData.append('color_palette', selectedStyles.color_palette);
      if (selectedStyles.character_style !== 'None') formData.append('character_style', selectedStyles.character_style);
      if (selectedStyles.line_style !== 'None') formData.append('line_style', selectedStyles.line_style);
      if (selectedStyles.composition !== 'None') formData.append('composition', selectedStyles.composition);
      formData.append('additional_notes', additionalNotes);

      const response = await axios.post(`${API_BASE_URL}/api/generate-manga-from-file`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      if (response.data.success) {
        setGalleryImages(response.data.gallery_images);
        setSceneDescriptions(response.data.scene_descriptions);
      } else {
        alert('Error: ' + response.data.message);
      }
    } catch (error) {
      console.error('Error generating manga from file:', error);
      alert('Error generating manga from file: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const regeneratePanel = async () => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('panel_number', panelNumber);
      formData.append('modification_request', modificationRequest);
      formData.append('replace_original', replaceOriginal);

      const response = await axios.post(`${API_BASE_URL}/api/regenerate-panel`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setRegenerationStatus(response.data.message);
        setRegeneratedImage(response.data.regenerated_image);
        if (response.data.updated_gallery && response.data.updated_gallery.length > 0) {
          setGalleryImages(response.data.updated_gallery);
        }
      } else {
        setRegenerationStatus('Error: ' + response.data.message);
      }
    } catch (error) {
      console.error('Error regenerating panel:', error);
      setRegenerationStatus('Error regenerating panel: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const createPDF = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/create-pdf`);
      
      if (response.data.success) {
        setPdfStatus(response.data.message);
        setPdfPath(response.data.pdf_path);
      } else {
        setPdfStatus('Error: ' + response.data.message);
      }
    } catch (error) {
      console.error('Error creating PDF:', error);
      setPdfStatus('Error creating PDF: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // Load task history
  const loadTaskHistory = async () => {
    try {
      // Use test session ID for now to see the test task
      const sessionId = getTestSessionId();
      console.log('Loading task history with session ID:', sessionId);
      const response = await axios.get(`${API_BASE_URL}/api/async/tasks`, {
        params: { session_id: sessionId, limit: 10, offset: 0 }
      });
      console.log('Task history response:', response.data);
      setTaskHistory(response.data.tasks || []);
    } catch (error) {
      console.error('Failed to load task history:', error);
    }
  };

  // Create PDF from specific task
  const createPDFFromTask = async (taskId) => {
    setLoading(true);
    setPdfStatus('');
    setPdfPath(null);
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/async/task/${taskId}/create-pdf`);
      
      if (response.data.success) {
        setPdfStatus(response.data.message);
        setPdfPath(response.data.pdf_path);
      } else {
        setPdfStatus('Error: ' + response.data.message);
      }
    } catch (error) {
      console.error('Error creating PDF from task:', error);
      setPdfStatus('Error creating PDF: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

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
            <img src={`${API_BASE_URL}${image}`} alt={`Panel ${index + 1}`} />
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
        <p>使用AI和自定义风格偏好将您的故事转化为漫画面板！</p>
      </header>

      <div className="tab-container">
        <div className="tab-buttons">
          <button 
            className={activeTab === 'generate-text' ? 'active' : ''}
            onClick={() => setActiveTab('generate-text')}
          >
            <FileText size={20} />
            Text Input
          </button>
          <button 
            className={activeTab === 'generate-file' ? 'active' : ''}
            onClick={() => setActiveTab('generate-file')}
          >
            <Upload size={20} />
            File Upload
          </button>
          <button 
            className={activeTab === 'regenerate' ? 'active' : ''}
            onClick={() => setActiveTab('regenerate')}
          >
            <RefreshCw size={20} />
            Regenerate Panels
          </button>
          <button 
            className={activeTab === 'pdf' ? 'active' : ''}
            onClick={() => setActiveTab('pdf')}
          >
            <Download size={20} />
            Download PDF
          </button>
          <button 
            className={activeTab === 'examples' ? 'active' : ''}
            onClick={() => setActiveTab('examples')}
          >
            <BookOpen size={20} />
            Examples
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'generate-text' && (
            <div className="generate-text-tab">
              <div className="input-section">
                <div className="story-input">
                  <label>Enter your story</label>
                  <textarea
                    value={storyText}
                    onChange={(e) => setStoryText(e.target.value)}
                    placeholder="Once upon a time..."
                    rows={10}
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

              <button 
                className="generate-btn"
                onClick={generateManga}
                disabled={loading || !storyText.trim()}
              >
                {loading ? (
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
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                      generateMangaFromFile(file);
                    }
                  }}
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
                  <label>Modification Instructions</label>
                  <textarea
                    value={modificationRequest}
                    onChange={(e) => setModificationRequest(e.target.value)}
                    placeholder="e.g., 'Make the lighting more dramatic', 'Change character expression to angry', 'Add more action lines'"
                    rows={3}
                  />
                </div>
                
                <div className="replace-option">
                  <label>
                    <input
                      type="checkbox"
                      checked={replaceOriginal}
                      onChange={(e) => setReplaceOriginal(e.target.checked)}
                    />
                    Replace original panel
                  </label>
                  <p><em>Check this to replace the original panel in the main gallery</em></p>
                </div>
                
                <button 
                  className="regenerate-btn"
                  onClick={regeneratePanel}
                  disabled={loading || !modificationRequest.trim()}
                >
                  {loading ? (
                    <>
                      <RefreshCw className="spinning" size={20} />
                      Regenerating...
                    </>
                  ) : (
                    <>
                      <RefreshCw size={20} />
                      Regenerate Panel
                    </>
                  )}
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
                  <img src={`${API_BASE_URL}${regeneratedImage}`} alt="Regenerated Panel" />
                </div>
              )}

              {galleryImages.length > 0 && (
                <ImageGallery images={galleryImages} title="Updated Main Gallery" />
              )}
            </div>
          )}

          {activeTab === 'pdf' && (
            <div className="pdf-tab">
              <h3>Export your manga as a PDF</h3>
              <p><strong>Note:</strong> Select a completed task below to create a PDF from it.</p>
              
              {/* Debug info */}
              <div style={{ marginBottom: '20px', padding: '10px', background: '#f0f0f0', borderRadius: '5px', fontSize: '12px' }}>
                <p>Debug: Task history length: {taskHistory.length}</p>
                <p>Debug: Completed tasks: {taskHistory.filter(task => task.status === 'COMPLETED').length}</p>
                <button onClick={loadTaskHistory} style={{ padding: '5px 10px', fontSize: '12px' }}>
                  Reload Tasks
                </button>
              </div>
              
              {/* Task List for PDF Creation */}
              <div className="pdf-task-list">
                <h4>Select a Completed Task</h4>
                {taskHistory.length === 0 ? (
                  <div className="no-tasks">
                    <p>No completed tasks available. Please generate manga first.</p>
                  </div>
                ) : (
                  <div className="task-list">
                    {/* Show all tasks for debugging, not just completed ones */}
                    {taskHistory.map((task, index) => (
                      <div key={task.task_id} className="task-item">
                        <div className="task-info">
                          <div className="task-header">
                            <span className="task-title">Task #{index + 1} - {task.status}</span>
                            <span className="task-panels">{task.total_panels} panels</span>
                          </div>
                          <div className="task-preview">
                            {task.story_preview}
                          </div>
                          <div className="task-date">
                            Created: {new Date(task.created_at).toLocaleString('zh-CN')}
                            {task.completed_at && (
                              <span> | Completed: {new Date(task.completed_at).toLocaleString('zh-CN')}</span>
                            )}
                          </div>
                        </div>
                        <div className="task-actions">
                          <button 
                            className="pdf-btn"
                            onClick={() => createPDFFromTask(task.task_id)}
                            disabled={loading || task.status !== 'COMPLETED'}
                          >
                            {loading ? (
                              <>
                                <RefreshCw className="spinning" size={16} />
                                Creating...
                              </>
                            ) : (
                              <>
                                <Download size={16} />
                                {task.status === 'COMPLETED' ? 'Create PDF' : `Status: ${task.status}`}
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {taskHistory.filter(task => task.status === 'COMPLETED').length === 0 && taskHistory.length > 0 && (
                  <div className="no-completed-tasks">
                    <p>No completed tasks available. Please wait for your manga generation to complete.</p>
                  </div>
                )}
              </div>

              {pdfStatus && (
                <div className="status-message">
                  <p>{pdfStatus}</p>
                </div>
              )}

              {pdfPath && (
                <div className="pdf-download">
                  <a href={`${API_BASE_URL}${pdfPath}`} download>
                    <button className="download-btn">
                      <Download size={20} />
                      Download PDF
                    </button>
                  </a>
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
                              <img src={`${API_BASE_URL}${exampleData.panels[selectedPanelIndex]}`} alt={`Manga panel ${selectedPanelIndex + 1}`} />
                            </div>
                            <div className="manga-thumbnails">
                              {console.log('Rendering thumbnails, panels:', exampleData.panels)}
                              {exampleData.panels.map((panel, index) => (
                                <div 
                                  key={index} 
                                  className={`thumbnail-item ${index === selectedPanelIndex ? 'active' : ''}`}
                                  onClick={() => setSelectedPanelIndex(index)}
                                >
                                  <img src={`${API_BASE_URL}${panel}`} alt={`Panel ${index + 1}`} />
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
}

export default App;
