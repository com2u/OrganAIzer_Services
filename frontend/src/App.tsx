import { useState } from 'react';
import TopNav from './components/TopNav';
import ExecutiveAgent from './components/ExecutiveAgent';
import TTSPage from './pages/TTSPage';
import STTPage from './pages/STTPage';
import ImageGenPage from './pages/ImageGenPage';
import YouTubePage from './pages/YouTubePage';
import IntegrationsPage from './pages/IntegrationsPage';
import PhonePage from './pages/PhonePage';

type PageType = 'executive' | 'tts' | 'stt' | 'image-gen' | 'youtube' | 'integrations' | 'phone';

const TABS: { id: PageType; label: string; active: string }[] = [
  { id: 'executive',    label: '🤖 Executive AI',  active: 'border-indigo-600 text-indigo-600' },
  { id: 'tts',          label: 'Text → Speech',    active: 'border-blue-600 text-blue-600' },
  { id: 'stt',          label: 'Speech → Text',    active: 'border-blue-600 text-blue-600' },
  { id: 'image-gen',    label: 'Text → Image',     active: 'border-purple-600 text-purple-600' },
  { id: 'youtube',      label: 'Video → Text',     active: 'border-red-600 text-red-600' },
  { id: 'integrations', label: '🔗 Integrations',  active: 'border-orange-600 text-orange-600' },
  { id: 'phone',        label: '📞 Phone',          active: 'border-green-600 text-green-600' },
];

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageType>('executive');

  return (
    <div className="min-h-screen bg-gray-100">
      <TopNav />

      {/* Tab navigation */}
      <div className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-30">
        <div className="container mx-auto px-4 max-w-5xl overflow-x-auto">
          <nav className="flex space-x-1 min-w-max">
            {TABS.map(({ id, label, active }) => (
              <button
                key={id}
                onClick={() => setCurrentPage(id)}
                className={`py-3.5 px-5 font-medium text-sm border-b-2 whitespace-nowrap transition-colors ${
                  currentPage === id
                    ? active
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main>
        {currentPage === 'executive'    && <ExecutiveAgent onPageChange={p => setCurrentPage(p as PageType)} />}
        {currentPage === 'tts'          && <TTSPage />}
        {currentPage === 'stt'          && <STTPage />}
        {currentPage === 'image-gen'    && <ImageGenPage />}
        {currentPage === 'youtube'      && <YouTubePage />}
        {currentPage === 'integrations' && <IntegrationsPage />}
        {currentPage === 'phone'        && <PhonePage />}
      </main>
    </div>
  );
}
