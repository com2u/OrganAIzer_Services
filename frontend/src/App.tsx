import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import YouTubeDownloader from './components/YouTubeDownloader';
import TextToSpeech from './components/TextToSpeech';
import SpeechToText from './components/SpeechToText';
import VideoToText from './components/VideoToText';
import TextToImage from './components/TextToImage';
import LLMInteraction from './components/LLMInteraction';
import GoogleIntegration from './components/GoogleIntegration';
import OutlookIntegration from './components/OutlookIntegration';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-100">
        <nav className="bg-blue-600 text-white p-4">
          <div className="container mx-auto flex space-x-4">
            <Link to="/youtube" className="hover:bg-blue-700 px-3 py-2 rounded">YouTube Downloader</Link>
            <Link to="/tts" className="hover:bg-blue-700 px-3 py-2 rounded">Text to Speech</Link>
            <Link to="/stt" className="hover:bg-blue-700 px-3 py-2 rounded">Speech to Text</Link>
            <Link to="/video-text" className="hover:bg-blue-700 px-3 py-2 rounded">Video to Text</Link>
            <Link to="/text-image" className="hover:bg-blue-700 px-3 py-2 rounded">Text to Image</Link>
            <Link to="/llm-interaction" className="hover:bg-blue-700 px-3 py-2 rounded">LLM Interaction</Link>
            <Link to="/google" className="hover:bg-blue-700 px-3 py-2 rounded">Google Integration</Link>
            <Link to="/outlook" className="hover:bg-blue-700 px-3 py-2 rounded">Outlook Integration</Link>
          </div>
        </nav>
        <main className="container mx-auto p-4">
          <Routes>
            <Route path="/youtube" element={<YouTubeDownloader />} />
            <Route path="/tts" element={<TextToSpeech />} />
            <Route path="/stt" element={<SpeechToText />} />
            <Route path="/video-text" element={<VideoToText />} />
            <Route path="/text-image" element={<TextToImage />} />
            <Route path="/llm-interaction" element={<LLMInteraction />} />
            <Route path="/google" element={<GoogleIntegration />} />
            <Route path="/outlook" element={<OutlookIntegration />} />
            <Route path="/" element={<div className="text-center mt-8"><h1 className="text-2xl">Welcome to OrganAIzer Service</h1><p>Select a tool from the navigation above.</p></div>} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
