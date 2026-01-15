import React, { useState, useEffect, useRef } from 'react';
import { chatCompletion, getAvailableModels, ChatMessage, ChatRequest, ModelInfo } from '../lib/api';
import ErrorBanner from '../components/ErrorBanner';

/**
 * ChatPage - LLM Chat Interface
 * Allows users to chat with various AI models via OpenRouter
 */
export default function ChatPage() {
  const [prompt, setPrompt] = useState('');
  const [conversationHistory, setConversationHistory] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [currentModel, setCurrentModel] = useState<string>('');
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [modelSearchTerm, setModelSearchTerm] = useState('');
  
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Load available models on mount
  useEffect(() => {
    loadAvailableModels();
  }, []);

  // Auto-scroll to bottom when conversation updates
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [conversationHistory]);

  const loadAvailableModels = async () => {
    try {
      const response = await getAvailableModels();
      setAvailableModels(response.models);
      setCurrentModel(response.current_model);
      setSelectedModel(response.current_model);
    } catch (err) {
      console.error('Failed to load models:', err);
      // Don't show error banner for this, just use default model
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!prompt.trim()) {
      return;
    }

    setError(null);
    setIsLoading(true);

    // Add user message to conversation
    const userMessage: ChatMessage = {
      role: 'user',
      content: prompt.trim()
    };
    
    const newHistory = [...conversationHistory, userMessage];
    setConversationHistory(newHistory);
    setPrompt('');

    try {
      const request: ChatRequest = {
        prompt: userMessage.content,
        model: selectedModel || undefined,
        conversation_history: conversationHistory,
        temperature: 0.7,
        max_tokens: 2000
      };

      const response = await chatCompletion(request);

      // Add assistant response to conversation
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response
      };
      
      setConversationHistory([...newHistory, assistantMessage]);
      
      // Update current model if it changed
      if (response.model !== currentModel) {
        setCurrentModel(response.model);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response from AI');
      // Remove the user message since we failed to get a response
      setConversationHistory(conversationHistory);
    } finally {
      setIsLoading(false);
    }
  };

  const clearConversation = () => {
    setConversationHistory([]);
    setError(null);
  };

  const filteredModels = availableModels.filter(model =>
    model.name.toLowerCase().includes(modelSearchTerm.toLowerCase()) ||
    model.id.toLowerCase().includes(modelSearchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Chat</h1>
          <p className="text-gray-600 mb-4">
            Chat with AI models powered by OpenRouter
          </p>
          
          {/* Model Selection */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Current Model
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowModelSelector(!showModelSelector)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-left text-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <span className="font-medium">{selectedModel || currentModel}</span>
                </button>
                {conversationHistory.length > 0 && (
                  <button
                    onClick={clearConversation}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                  >
                    Clear Chat
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Model Selector Dropdown */}
          {showModelSelector && (
            <div className="mt-4 border border-gray-300 rounded-lg p-4 bg-gray-50">
              <input
                type="text"
                placeholder="Search models..."
                value={modelSearchTerm}
                onChange={(e) => setModelSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="max-h-60 overflow-y-auto space-y-1">
                {filteredModels.length > 0 ? (
                  filteredModels.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => {
                        setSelectedModel(model.id);
                        setShowModelSelector(false);
                        setModelSearchTerm('');
                      }}
                      className={`w-full text-left px-3 py-2 rounded hover:bg-gray-200 ${
                        selectedModel === model.id ? 'bg-blue-100 font-medium' : ''
                      }`}
                    >
                      <div className="text-sm font-medium">{model.name}</div>
                      <div className="text-xs text-gray-500">{model.id}</div>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-gray-500 text-center py-4">No models found</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6">
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* Chat Container */}
        <div className="bg-white rounded-lg shadow-sm mb-6 flex flex-col h-[500px]">
          {/* Messages */}
          <div
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto p-6 space-y-4"
          >
            {conversationHistory.length === 0 ? (
              <div className="text-center text-gray-500 mt-20">
                <p className="text-lg font-medium mb-2">No messages yet</p>
                <p className="text-sm">Start a conversation by typing a message below</p>
              </div>
            ) : (
              conversationHistory.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <div className="text-xs font-medium mb-1 opacity-75">
                      {message.role === 'user' ? 'You' : 'AI'}
                    </div>
                    <div className="whitespace-pre-wrap break-words">{message.content}</div>
                  </div>
                </div>
              ))
            )}
            
            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input Form */}
          <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
            <div className="flex gap-2">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                placeholder="Type your message... (Shift+Enter for new line, Enter to send)"
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !prompt.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-300 disabled:cursor-not-allowed self-end"
              >
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </form>
        </div>

        {/* Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">💡 Tips</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Use Shift+Enter to create a new line, Enter to send</li>
            <li>• Click "Current Model" to switch between different AI models</li>
            <li>• Conversation history is maintained across messages</li>
            <li>• Click "Clear Chat" to start a fresh conversation</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
