// Note: The _execute_action command automatically opens the popup
// No custom command handling needed for that

// Create context menu items
chrome.runtime.onInstalled.addListener(() => {
  // Create parent menu
  chrome.contextMenus.create({
    id: 'organAIzer',
    title: 'OrganAIzer',
    contexts: ['selection']
  });
  
  // Text to Speech
  chrome.contextMenus.create({
    id: 'textToSpeech',
    parentId: 'organAIzer',
    title: '🔊 Read Aloud',
    contexts: ['selection']
  });
  
  // Text to Summary
  chrome.contextMenus.create({
    id: 'textToSummary',
    parentId: 'organAIzer',
    title: '📝 Summarize',
    contexts: ['selection']
  });
  
  // Translate
  chrome.contextMenus.create({
    id: 'translate',
    parentId: 'organAIzer',
    title: '🌐 Translate',
    contexts: ['selection']
  });
  
  // Text to Image
  chrome.contextMenus.create({
    id: 'textToImage',
    parentId: 'organAIzer',
    title: '🖼️ Generate Image',
    contexts: ['selection']
  });

  // Remove Empty Lines
  chrome.contextMenus.create({
    id: 'removeEmptyLines',
    parentId: 'organAIzer',
    title: '🧹 Remove Empty Lines',
    contexts: ['selection']
  });
  
  // Separator
  chrome.contextMenus.create({
    id: 'separator',
    parentId: 'organAIzer',
    type: 'separator',
    contexts: ['selection']
  });
  
  // Dictation (available on all pages, not just selection)
  chrome.contextMenus.create({
    id: 'dictation',
    parentId: 'organAIzer',
    title: '🎤 Start Dictation',
    contexts: ['editable']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  const action = info.menuItemId;
  
  if (action !== 'organAIzer' && action !== 'separator') {
    chrome.tabs.sendMessage(tab.id, { action });
  }
});

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener((command) => {
  if (command === 'removeEmptyLines') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'removeEmptyLines' });
      }
    });
  }
});

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Handle any background tasks if needed
  if (request.type === 'background-task') {
    // Process background tasks here
    sendResponse({ success: true });
  }
  return true;
});
