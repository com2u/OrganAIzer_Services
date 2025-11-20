/**
 * Main application component.
 * Sets up the app layout with top navigation and routes to different pages.
 */

import TopNav from './components/TopNav';
import TTSPage from './pages/TTSPage';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <TopNav />
      <main>
        <TTSPage />
      </main>
    </div>
  );
}
