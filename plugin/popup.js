// Default settings
const DEFAULT_SETTINGS = {
  apiUrl: 'http://localhost:8000',
  apiKey: '',
  summaryPrompt: 'Summarize the following text in a concise manner, highlighting the key points:\n\n{text}',
  translatePrompt: 'Translate the following text to English:\n\n{text}',
  dictationLanguage: 'en-US'
};

// Dictation language options
const LANGUAGE_OPTIONS = [
  { code: 'en-US', name: 'English (US)' },
  { code: 'en-GB', name: 'English (UK)' },
  { code: 'de-DE', name: 'German' },
  { code: 'fr-FR', name: 'French' },
  { code: 'es-ES', name: 'Spanish' },
  { code: 'it-IT', name: 'Italian' },
  { code: 'pt-BR', name: 'Portuguese (Brazil)' },
  { code: 'nl-NL', name: 'Dutch' },
  { code: 'pl-PL', name: 'Polish' },
  { code: 'ru-RU', name: 'Russian' },
  { code: 'ja-JP', name: 'Japanese' },
  { code: 'ko-KR', name: 'Korean' },
  { code: 'zh-CN', name: 'Chinese (Simplified)' }
];

// Load settings and prompts from storage
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);

    document.getElementById('apiUrl').value = settings.apiUrl || DEFAULT_SETTINGS.apiUrl;
    document.getElementById('apiKey').value = settings.apiKey || '';
    document.getElementById('summaryPrompt').value = settings.summaryPrompt || DEFAULT_SETTINGS.summaryPrompt;
    document.getElementById('translatePrompt').value = settings.translatePrompt || DEFAULT_SETTINGS.translatePrompt;
    
    // Populate language dropdown
    const langSelect = document.getElementById('dictationLanguage');
    if (langSelect) {
      LANGUAGE_OPTIONS.forEach(lang => {
        const option = document.createElement('option');
        option.value = lang.code;
        option.textContent = lang.name;
        if (lang.code === (settings.dictationLanguage || DEFAULT_SETTINGS.dictationLanguage)) {
          option.selected = true;
        }
        langSelect.appendChild(option);
      });
    }
    
    // Check connection status on load
    checkConnectionStatus();
  } catch (error) {
    console.error('Failed to load settings:', error);
    showStatus('settingsStatus', 'Failed to load settings', 'error');
  }
});

// Check backend connection status
async function checkConnectionStatus() {
  const statusEl = document.getElementById('connectionStatus');
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  
  if (!statusEl) return;
  
  statusDot.className = 'status-dot checking';
  statusText.textContent = 'Checking...';
  
  try {
    const settings = await chrome.storage.sync.get({ apiUrl: DEFAULT_SETTINGS.apiUrl });
    const apiUrl = settings.apiUrl || DEFAULT_SETTINGS.apiUrl;
    
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    
    const response = await fetch(`${apiUrl}/health`, {
      method: 'GET',
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    
    if (response.ok) {
      statusDot.className = 'status-dot connected';
      statusText.textContent = 'Connected';
    } else {
      statusDot.className = 'status-dot error';
      statusText.textContent = `Error (${response.status})`;
    }
  } catch (error) {
    statusDot.className = 'status-dot disconnected';
    if (error.name === 'AbortError') {
      statusText.textContent = 'Timeout';
    } else {
      statusText.textContent = 'Disconnected';
    }
  }
}

// Save settings
document.getElementById('saveSettings').addEventListener('click', async () => {
  const apiUrl = document.getElementById('apiUrl').value.trim();
  const apiKey = document.getElementById('apiKey').value.trim();
  const dictationLanguage = document.getElementById('dictationLanguage')?.value || DEFAULT_SETTINGS.dictationLanguage;

  // Validate URL
  if (!apiUrl) {
    showStatus('settingsStatus', 'Backend URL is required', 'error');
    return;
  }
  
  try {
    new URL(apiUrl);
  } catch {
    showStatus('settingsStatus', 'Invalid URL format', 'error');
    return;
  }

  try {
    await chrome.storage.sync.set({ apiUrl, apiKey, dictationLanguage });
    showStatus('settingsStatus', 'Settings saved successfully!', 'success');
    
    // Re-check connection with new settings
    checkConnectionStatus();
  } catch (error) {
    showStatus('settingsStatus', 'Failed to save settings', 'error');
  }
});

// Test connection button
document.getElementById('testConnection')?.addEventListener('click', async () => {
  checkConnectionStatus();
  showStatus('settingsStatus', 'Testing connection...', 'info');
});

// Save prompts
document.getElementById('savePrompts').addEventListener('click', async () => {
  const summaryPrompt = document.getElementById('summaryPrompt').value;
  const translatePrompt = document.getElementById('translatePrompt').value;

  // Validate prompts contain placeholder
  if (!summaryPrompt.includes('{text}')) {
    showStatus('promptsStatus', 'Summary prompt must contain {text} placeholder', 'error');
    return;
  }
  
  if (!translatePrompt.includes('{text}')) {
    showStatus('promptsStatus', 'Translation prompt must contain {text} placeholder', 'error');
    return;
  }

  try {
    await chrome.storage.sync.set({ summaryPrompt, translatePrompt });
    showStatus('promptsStatus', 'Prompts saved successfully!', 'success');
  } catch (error) {
    showStatus('promptsStatus', 'Failed to save prompts', 'error');
  }
});

// Reset prompts to defaults
document.getElementById('resetPrompts')?.addEventListener('click', async () => {
  document.getElementById('summaryPrompt').value = DEFAULT_SETTINGS.summaryPrompt;
  document.getElementById('translatePrompt').value = DEFAULT_SETTINGS.translatePrompt;
  
  try {
    await chrome.storage.sync.set({
      summaryPrompt: DEFAULT_SETTINGS.summaryPrompt,
      translatePrompt: DEFAULT_SETTINGS.translatePrompt
    });
    showStatus('promptsStatus', 'Prompts reset to defaults', 'success');
  } catch (error) {
    showStatus('promptsStatus', 'Failed to reset prompts', 'error');
  }
});

// Action buttons
document.getElementById('textToSpeech').addEventListener('click', () => {
  executeAction('textToSpeech');
});

document.getElementById('textToSummary').addEventListener('click', () => {
  executeAction('textToSummary');
});

document.getElementById('dictation').addEventListener('click', () => {
  executeAction('dictation');
});

document.getElementById('textToImage').addEventListener('click', () => {
  executeAction('textToImage');
});

document.getElementById('translate').addEventListener('click', () => {
  executeAction('translate');
});

document.getElementById('removeEmptyLines').addEventListener('click', () => {
  executeAction('removeEmptyLines');
});

// Execute action in active tab
async function executeAction(action) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab) {
      console.error('No active tab found');
      return;
    }
    
    // Check if we can inject into this tab
    if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
      alert('This extension cannot work on Chrome system pages. Please try on a regular webpage.');
      return;
    }
    
    chrome.tabs.sendMessage(tab.id, { action }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Error:', chrome.runtime.lastError.message);
        // Content script might not be loaded, try injecting it
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        }).then(() => {
          // Retry sending the message
          setTimeout(() => {
            chrome.tabs.sendMessage(tab.id, { action });
          }, 100);
        }).catch(err => {
          console.error('Failed to inject content script:', err);
          alert('Failed to activate on this page. Try refreshing the page.');
        });
      }
    });
    
    window.close();
  } catch (error) {
    console.error('Execute action error:', error);
  }
}

// Show status message
function showStatus(elementId, message, type) {
  const statusEl = document.getElementById(elementId);
  if (!statusEl) return;
  
  statusEl.textContent = message;
  statusEl.className = `status-message ${type}`;
  statusEl.style.display = 'block';
  
  setTimeout(() => {
    statusEl.style.display = 'none';
    statusEl.className = 'status-message';
    statusEl.textContent = '';
  }, 3000);
}
