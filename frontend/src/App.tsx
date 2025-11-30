/**
 * Main application component.
 * Sets up the app layout with top navigation and routes to different pages.
 */

import { useState } from 'react';
import TopNav from './components/TopNav';
import TTSPage from './pages/TTSPage';
import STTPage from './pages/STTPage';
import ImageGenPage from './pages/ImageGenPage';

type PageType = 'tts' | 'stt' | 'image-gen';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageType>('tts');

  return (
    <div className="min-h-screen bg-gray-100">
      <TopNav />
      
      {/* Page Navigation Tabs */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="container mx-auto px-4 max-w-4xl">
          <nav className="flex space-x-4">
            <button
              onClick={() => setCurrentPage('tts')}
              className={`py-4 px-6 font-medium text-sm border-b-2 transition-colors ${
                currentPage === 'tts'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
              }`}
            >
              Text → Speech
            </button>
            <button
              onClick={() => setCurrentPage('stt')}
              className={`py-4 px-6 font-medium text-sm border-b-2 transition-colors ${
                currentPage === 'stt'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
              }`}
            >
              Speech → Text
            </button>
            <button
              onClick={() => setCurrentPage('image-gen')}
              className={`py-4 px-6 font-medium text-sm border-b-2 transition-colors ${
                currentPage === 'image-gen'
                  ? 'border-purple-600 text-purple-600'
                  : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
              }`}
            >
              Text → Image
            </button>
          </nav>
        </div>
      </div>

      <main>
        {currentPage === 'tts' && <TTSPage />}
        {currentPage === 'stt' && <STTPage />}
        {currentPage === 'image-gen' && <ImageGenPage />}
      </main>
    </div>
  );
}
