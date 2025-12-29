// Default settings
const DEFAULT_SETTINGS = {
  apiUrl: 'http://localhost:8000',
  apiKey: '',
  summaryPrompt: 'Summarize the following text in a concise manner, highlighting the key points:\n\n{text}',
  translatePrompt: 'Translate the following text to English:\n\n{text}',
  dictationLanguage: 'en-US'
};

// Listen for messages from popup and background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action) {
    handleAction(request.action);
    sendResponse({ success: true });
  }
  return true;
});

// Handle different actions
async function handleAction(action) {
  switch (action) {
    case 'textToSpeech':
      await handleTextToSpeech();
      break;
    case 'textToSummary':
      await handleTextToSummary();
      break;
    case 'dictation':
      await handleDictation();
      break;
    case 'textToImage':
      await handleTextToImage();
      break;
    case 'translate':
      await handleTranslate();
      break;
  }
}

// Get settings with defaults
async function getSettings() {
  try {
    const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
    return { ...DEFAULT_SETTINGS, ...settings };
  } catch (error) {
    console.error('Failed to load settings:', error);
    return DEFAULT_SETTINGS;
  }
}

// Helper function to build headers with API key
function buildHeaders(apiKey, contentType = 'application/json') {
  const headers = {};
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  return headers;
}

// Copy text to clipboard
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
}

// Copy image to clipboard
async function copyImageToClipboard(imageSrc) {
  try {
    const response = await fetch(imageSrc);
    const blob = await response.blob();
    await navigator.clipboard.write([
      new ClipboardItem({ [blob.type]: blob })
    ]);
    return true;
  } catch (error) {
    console.error('Failed to copy image to clipboard:', error);
    return false;
  }
}

// Get selected text
function getSelectedText() {
  const selection = window.getSelection();
  return selection.toString().trim();
}

// Get cursor position and focused element
function getCursorInfo() {
  const activeElement = document.activeElement;
  let cursorPosition = null;
  
  if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT')) {
    cursorPosition = activeElement.selectionStart;
  } else if (activeElement && activeElement.isContentEditable) {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
      cursorPosition = selection.getRangeAt(0);
    }
  }
  
  return { element: activeElement, position: cursorPosition };
}

// Insert text at cursor position
function insertTextAtCursor(text) {
  const { element, position } = getCursorInfo();
  
  if (!element) {
    showNotification('No active text field found', 'error');
    return;
  }
  
  if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
    const currentValue = element.value;
    const start = element.selectionStart;
    const end = element.selectionEnd;
    
    element.value = currentValue.substring(0, start) + text + currentValue.substring(end);
    element.selectionStart = element.selectionEnd = start + text.length;
    
    // Trigger input event for frameworks like React
    element.dispatchEvent(new Event('input', { bubbles: true }));
  } else if (element.isContentEditable && position) {
    const textNode = document.createTextNode(text);
    position.deleteContents();
    position.insertNode(textNode);
    position.setStartAfter(textNode);
    position.setEndAfter(textNode);
  }
}

// Insert image at cursor position
function insertImageAtCursor(imageData) {
  const { element, position } = getCursorInfo();
  
  // Determine if imageData is base64 or URL
  let imageSrc = imageData;
  if (imageData && !imageData.startsWith('http') && !imageData.startsWith('data:')) {
    // Assume base64 if no prefix
    imageSrc = `data:image/png;base64,${imageData}`;
  }
  
  if (!element) {
    // No active element - open image in new tab instead
    showImageModal(imageSrc);
    return;
  }
  
  const img = document.createElement('img');
  img.src = imageSrc;
  img.style.maxWidth = '100%';
  img.style.height = 'auto';
  img.alt = 'Generated image';
  
  if (element.isContentEditable && position) {
    position.deleteContents();
    position.insertNode(img);
    position.setStartAfter(img);
    position.setEndAfter(img);
    showNotification('Image inserted!', 'success');
  } else {
    // For non-contenteditable fields, show image in modal
    showImageModal(imageSrc);
  }
}

// Show image in a modal overlay
function showImageModal(imageSrc) {
  // Remove existing modal
  const existingModal = document.getElementById('organAIzer-image-modal');
  if (existingModal) {
    existingModal.remove();
  }
  
  const modal = document.createElement('div');
  modal.id = 'organAIzer-image-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.8);
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 20px;
  `;
  
  const img = document.createElement('img');
  img.src = imageSrc;
  img.style.cssText = `
    max-width: 90%;
    max-height: 70%;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  `;
  
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    gap: 10px;
  `;
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '⬇️ Download';
  downloadBtn.style.cssText = `
    padding: 10px 20px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  `;
  downloadBtn.onclick = () => {
    const a = document.createElement('a');
    a.href = imageSrc;
    a.download = 'generated-image.png';
    a.click();
  };
  
  const copyBtn = document.createElement('button');
  copyBtn.textContent = '📋 Copy to Clipboard';
  copyBtn.style.cssText = `
    padding: 10px 20px;
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  `;
  copyBtn.onclick = async () => {
    try {
      const response = await fetch(imageSrc);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
      showNotification('Image copied to clipboard!', 'success');
    } catch (error) {
      showNotification('Failed to copy image', 'error');
    }
  };
  
  const closeBtn = document.createElement('button');
  closeBtn.textContent = '✕ Close';
  closeBtn.style.cssText = `
    padding: 10px 20px;
    background-color: #f44336;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  `;
  closeBtn.onclick = () => modal.remove();
  
  buttonContainer.appendChild(downloadBtn);
  buttonContainer.appendChild(copyBtn);
  buttonContainer.appendChild(closeBtn);
  
  modal.appendChild(img);
  modal.appendChild(buttonContainer);
  
  // Close on background click
  modal.onclick = (e) => {
    if (e.target === modal) {
      modal.remove();
    }
  };
  
  // Close on Escape key
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
  
  document.body.appendChild(modal);
  showNotification('Image generated! Click to download or copy.', 'success');
}

// Replace selected text
function replaceSelectedText(newText) {
  const { element } = getCursorInfo();
  
  if (!element) {
    showNotification('No active text field found', 'error');
    return;
  }
  
  if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
    const start = element.selectionStart;
    const end = element.selectionEnd;
    const currentValue = element.value;
    
    element.value = currentValue.substring(0, start) + newText + currentValue.substring(end);
    element.selectionStart = start;
    element.selectionEnd = start + newText.length;
    
    element.dispatchEvent(new Event('input', { bubbles: true }));
  } else if (element.isContentEditable) {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(newText);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.setEndAfter(textNode);
    }
  }
}

// Text to Speech
async function handleTextToSpeech() {
  const text = getSelectedText();
  
  if (!text) {
    showNotification('Please select some text first', 'error');
    return;
  }
  
  showNotification('🔊 Generating speech...', 'loading');
  
  try {
    const settings = await getSettings();
    const response = await fetch(`${settings.apiUrl}/api/tts/generate`, {
      method: 'POST',
      headers: buildHeaders(settings.apiKey),
      body: JSON.stringify({ text_md: text })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    const audioUrl = `${settings.apiUrl}${data.audio_url}`;
    
    // Play audio
    const audio = new Audio(audioUrl);
    audio.onerror = () => {
      showNotification('Failed to play audio', 'error');
    };
    audio.onended = () => {
      showNotification('Audio finished', 'success');
    };
    audio.play();
    
    showNotification('🔊 Playing audio...', 'success');
  } catch (error) {
    console.error('Text to speech error:', error);
    showNotification(`Failed to generate speech: ${error.message}`, 'error');
  }
}

// Text to Summary
async function handleTextToSummary() {
  const text = getSelectedText();
  
  if (!text) {
    showNotification('Please select some text first', 'error');
    return;
  }
  
  showNotification('📝 Generating summary...', 'loading');
  
  try {
    const settings = await getSettings();
    const prompt = (settings.summaryPrompt || DEFAULT_SETTINGS.summaryPrompt).replace('{text}', text);
    
    const response = await fetch(`${settings.apiUrl}/api/llm`, {
      method: 'POST',
      headers: buildHeaders(settings.apiKey),
      body: JSON.stringify({ prompt })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    const summary = data.response || data.text || data.result;
    
    if (!summary) {
      throw new Error('Empty response from server');
    }
    
    // Copy to clipboard
    const copied = await copyToClipboard(summary);
    
    // Also try to insert at cursor
    insertTextAtCursor('\n\n📝 Summary:\n' + summary + '\n\n');
    
    if (copied) {
      showNotification('📝 Summary generated and copied to clipboard!', 'success');
    } else {
      showNotification('Summary inserted!', 'success');
    }
  } catch (error) {
    console.error('Text to summary error:', error);
    showNotification(`Failed to generate summary: ${error.message}`, 'error');
  }
}

// Dictation (Speech to Text)
async function handleDictation() {
  // Use Web Speech API for dictation
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    showNotification('Speech recognition not supported in this browser. Try Chrome or Edge.', 'error');
    return;
  }
  
  const settings = await getSettings();
  
  showNotification('🎤 Listening... Speak now!', 'loading');
  
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = settings.dictationLanguage || 'en-US';
  
  let finalTranscript = '';
  
  recognition.onresult = (event) => {
    let interimTranscript = '';
    
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }
    
    if (interimTranscript) {
      showNotification(`🎤 Hearing: "${interimTranscript}"`, 'loading');
    }
  };
  
  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    let errorMessage = 'Dictation failed: ';
    switch (event.error) {
      case 'not-allowed':
        errorMessage += 'Microphone access denied. Please allow microphone access.';
        break;
      case 'no-speech':
        errorMessage += 'No speech detected. Try again.';
        break;
      case 'network':
        errorMessage += 'Network error. Check your connection.';
        break;
      default:
        errorMessage += event.error;
    }
    showNotification(errorMessage, 'error');
  };
  
  recognition.onend = () => {
    if (finalTranscript) {
      insertTextAtCursor(finalTranscript);
      showNotification('✓ Text inserted!', 'success');
    }
  };
  
  try {
    recognition.start();
  } catch (error) {
    showNotification('Failed to start dictation: ' + error.message, 'error');
  }
}

// Text to Image
async function handleTextToImage() {
  const text = getSelectedText();
  
  if (!text) {
    showNotification('Please select some text first', 'error');
    return;
  }
  
  showNotification('🖼️ Generating image... This may take a moment.', 'loading');
  
  try {
    const settings = await getSettings();
    
    const formData = new FormData();
    formData.append('prompt', text);
    
    const headers = {};
    if (settings.apiKey) {
      headers['X-API-Key'] = settings.apiKey;
    }
    
    const response = await fetch(`${settings.apiUrl}/api/text-image/generate`, {
      method: 'POST',
      headers: headers,
      body: formData
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    
    // Handle different response formats
    let imageData = null;
    if (data.images && data.images.length > 0) {
      imageData = data.images[0];
    } else if (data.image) {
      imageData = data.image;
    } else if (data.url) {
      imageData = data.url;
    } else if (data.base64) {
      imageData = data.base64;
    }
    
    if (imageData) {
      // Prepare image source
      let imageSrc = imageData;
      if (imageData && !imageData.startsWith('http') && !imageData.startsWith('data:')) {
        imageSrc = `data:image/png;base64,${imageData}`;
      }
      
      // Copy image to clipboard
      const copied = await copyImageToClipboard(imageSrc);
      
      // Also show/insert the image
      insertImageAtCursor(imageData);
      
      if (copied) {
        showNotification('🖼️ Image generated and copied to clipboard!', 'success');
      }
    } else {
      showNotification('No image in response', 'error');
    }
  } catch (error) {
    console.error('Text to image error:', error);
    showNotification(`Failed to generate image: ${error.message}`, 'error');
  }
}

// Translate
async function handleTranslate() {
  const text = getSelectedText();
  
  if (!text) {
    showNotification('Please select some text first', 'error');
    return;
  }
  
  showNotification('🌐 Translating...', 'loading');
  
  try {
    const settings = await getSettings();
    const prompt = (settings.translatePrompt || DEFAULT_SETTINGS.translatePrompt).replace('{text}', text);
    
    const response = await fetch(`${settings.apiUrl}/api/llm`, {
      method: 'POST',
      headers: buildHeaders(settings.apiKey),
      body: JSON.stringify({ prompt })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    const translation = data.response || data.text || data.result;
    
    if (!translation) {
      throw new Error('Empty response from server');
    }
    
    // Copy to clipboard
    const copied = await copyToClipboard(translation);
    
    // Also replace selected text
    replaceSelectedText(translation);
    
    if (copied) {
      showNotification('🌐 Translation complete and copied to clipboard!', 'success');
    } else {
      showNotification('🌐 Translation complete!', 'success');
    }
  } catch (error) {
    console.error('Translation error:', error);
    showNotification(`Failed to translate: ${error.message}`, 'error');
  }
}

// Show notification
function showNotification(message, type = 'info') {
  // Remove existing notification (unless loading - allow stacking)
  const existing = document.getElementById('organAIzer-notification');
  if (existing && type !== 'loading') {
    existing.remove();
  } else if (existing && type === 'loading') {
    // Update existing loading notification
    existing.textContent = message;
    return;
  }
  
  // Determine background color
  let bgColor = '#2196F3'; // info - blue
  if (type === 'error') bgColor = '#f44336'; // red
  else if (type === 'success') bgColor = '#4CAF50'; // green
  else if (type === 'warning') bgColor = '#ff9800'; // orange
  else if (type === 'loading') bgColor = '#9C27B0'; // purple
  
  // Create notification element
  const notification = document.createElement('div');
  notification.id = 'organAIzer-notification';
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 15px 20px;
    background-color: ${bgColor};
    color: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 999999;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    max-width: 350px;
    animation: slideIn 0.3s ease-out;
    display: flex;
    align-items: center;
    gap: 10px;
  `;
  
  // Add spinner for loading state
  if (type === 'loading') {
    const spinner = document.createElement('div');
    spinner.style.cssText = `
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    `;
    notification.appendChild(spinner);
  }
  
  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  notification.appendChild(textSpan);
  
  document.body.appendChild(notification);
  
  // Auto-remove after delay (longer for loading)
  const timeout = type === 'loading' ? 30000 : 4000;
  setTimeout(() => {
    if (notification.parentNode) {
      notification.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.remove();
        }
      }, 300);
    }
  }, timeout);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
  
  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
`;
document.head.appendChild(style);
