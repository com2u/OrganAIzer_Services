/**
 * Text-to-Speech page component.
 * Main interface for the TTS tool where users can input markdown text,
 * generate speech, and download/play the resulting audio.
 */

import { useState } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import AudioPlayer from '../components/AudioPlayer';
import { generateSpeech, getFullAudioUrl } from '../lib/api';

export default function TTSPage() {
  const [inputText, setInputText] = useState('');
  const [normalizedText, setNormalizedText] = useState('');
  const [language, setLanguage] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  /**
   * Handles the speech generation process.
   * Calls the backend API and updates the UI with the results.
   */
  const handleGenerateSpeech = async () => {
    // Clear previous results and errors
    setError('');
    setNormalizedText('');
    setLanguage('');
    setAudioUrl('');

    // Validate input
    if (!inputText.trim()) {
      setError('Please enter some text to convert to speech');
      return;
    }

    setIsLoading(true);

    try {
      const response = await generateSpeech(inputText);
      
      setNormalizedText(response.text_normalized);
      setLanguage(response.language);
      setAudioUrl(getFullAudioUrl(response.audio_url));
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
      console.error('TTS generation error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Text-to-Speech</h2>
      
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <div className="bg-white shadow-md rounded-lg p-6">
        <div className="mb-6">
          <label htmlFor="markdown-input" className="block text-sm font-medium text-gray-700 mb-2">
            Enter Markdown Text
          </label>
          <textarea
            id="markdown-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="# Hello World&#10;&#10;Enter your **markdown** text here...&#10;&#10;- Item 1&#10;- Item 2"
            className="w-full h-48 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            disabled={isLoading}
          />
        </div>

        <button
          onClick={handleGenerateSpeech}
          disabled={isLoading}
          className={`w-full py-3 px-4 rounded-md font-medium text-white transition-colors ${
            isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          {isLoading ? 'Generating Speech...' : 'Generate Speech'}
        </button>
      </div>

      {/* Results section */}
      {(normalizedText || audioUrl) && (
        <div className="mt-8 bg-white shadow-md rounded-lg p-6">
          <h3 className="text-xl font-semibold mb-4 text-gray-800">Results</h3>
          
          {normalizedText && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Normalized Text
              </label>
              <div className="bg-gray-50 p-4 rounded-md border border-gray-200">
                <p className="text-gray-800 whitespace-pre-wrap">{normalizedText}</p>
              </div>
            </div>
          )}

          {language && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Detected Language
              </label>
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                <p className="text-gray-800 font-mono">{language}</p>
              </div>
            </div>
          )}

          {audioUrl && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Generated Audio
              </label>
              <AudioPlayer audioUrl={audioUrl} />
              <a
                href={audioUrl}
                download
                className="mt-3 inline-block px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                Download MP3
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
