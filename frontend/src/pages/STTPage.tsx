/**
 * Speech-to-Text page component.
 * Main interface for the STT tool where users can upload audio files,
 * transcribe them, and view/copy the resulting text.
 */

import { useState, useRef } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import { transcribeAudio } from '../lib/api';

export default function STTPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState('');
  const [detectedLanguage, setDetectedLanguage] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('auto');
  const [duration, setDuration] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  /**
   * Handles file selection from the file input.
   */
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      const allowedTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/m4a', 'audio/ogg', 'audio/flac'];
      const allowedExtensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac'];
      const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
      
      if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        setError('Please select a valid audio file (MP3, WAV, M4A, OGG, or FLAC)');
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      // Validate file size (25MB max)
      const maxSizeMB = 25;
      if (file.size > maxSizeMB * 1024 * 1024) {
        setError(`File size must be less than ${maxSizeMB}MB`);
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      setSelectedFile(file);
      setError('');
    }
  };

  /**
   * Handles the transcription process.
   * Calls the backend API and updates the UI with the results.
   */
  const handleTranscribe = async () => {
    if (!selectedFile) {
      setError('Please select an audio file first');
      return;
    }

    // Clear previous results and errors
    setError('');
    setTranscript('');
    setDetectedLanguage('');
    setDuration(null);

    setIsLoading(true);

    try {
      // Pass language hint if not auto-detect
      const languageHint = selectedLanguage === 'auto' ? undefined : selectedLanguage;
      const response = await transcribeAudio(selectedFile, languageHint);
      
      setTranscript(response.transcript);
      setDetectedLanguage(response.language || '');
      setDuration(response.duration_seconds || null);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
      console.error('STT transcription error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handles copying the transcript to clipboard.
   */
  const handleCopyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(transcript);
      // Could add a toast notification here
      alert('Transcript copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      setError('Failed to copy to clipboard');
    }
  };

  /**
   * Formats file size for display.
   */
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  /**
   * Formats duration for display.
   */
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Speech-to-Text</h2>
      
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <div className="bg-white shadow-md rounded-lg p-6">
        <div className="mb-6">
          <label htmlFor="audio-input" className="block text-sm font-medium text-gray-700 mb-2">
            Upload Audio File
          </label>
          <input
            id="audio-input"
            ref={fileInputRef}
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac,audio/mpeg,audio/wav,audio/m4a,audio/ogg,audio/flac"
            onChange={handleFileChange}
            disabled={isLoading}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <p className="mt-2 text-sm text-gray-500">
            Supported formats: MP3, WAV, M4A, OGG, FLAC (max 25MB)
          </p>
        </div>

        <div className="mb-6">
          <label htmlFor="language-select" className="block text-sm font-medium text-gray-700 mb-2">
            Language (for better accuracy)
          </label>
          <select
            id="language-select"
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
            disabled={isLoading}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="auto">Auto-detect</option>
            <option value="en">English</option>
            <option value="de">German (Deutsch)</option>
            <option value="es">Spanish (Español)</option>
            <option value="fr">French (Français)</option>
            <option value="it">Italian (Italiano)</option>
            <option value="pt">Portuguese (Português)</option>
            <option value="nl">Dutch (Nederlands)</option>
            <option value="pl">Polish (Polski)</option>
            <option value="ru">Russian (Русский)</option>
            <option value="ja">Japanese (日本語)</option>
            <option value="zh">Chinese (中文)</option>
          </select>
          <p className="mt-2 text-sm text-gray-500">
            💡 Tip: Selecting the correct language improves accuracy significantly
          </p>
        </div>

        {selectedFile && (
          <div className="mb-6 p-4 bg-gray-50 rounded-md border border-gray-200">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Selected File</h3>
            <div className="text-sm text-gray-600">
              <p><span className="font-medium">Name:</span> {selectedFile.name}</p>
              <p><span className="font-medium">Size:</span> {formatFileSize(selectedFile.size)}</p>
              <p><span className="font-medium">Type:</span> {selectedFile.type || 'Unknown'}</p>
            </div>
          </div>
        )}

        <button
          onClick={handleTranscribe}
          disabled={!selectedFile || isLoading}
          className={`w-full py-3 px-4 rounded-md font-medium text-white transition-colors ${
            !selectedFile || isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          {isLoading ? 'Transcribing Audio...' : 'Transcribe Audio'}
        </button>
      </div>

      {/* Results section */}
      {transcript && (
        <div className="mt-8 bg-white shadow-md rounded-lg p-6">
          <h3 className="text-xl font-semibold mb-4 text-gray-800">Transcription Results</h3>
          
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Transcript
              </label>
              <button
                onClick={handleCopyToClipboard}
                className="px-3 py-1 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
              >
                Copy to Clipboard
              </button>
            </div>
            <div className="bg-gray-50 p-4 rounded-md border border-gray-200 max-h-96 overflow-y-auto">
              <p className="text-gray-800 whitespace-pre-wrap">{transcript}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {detectedLanguage && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Detected Language
                </label>
                <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                  <p className="text-gray-800 font-mono">{detectedLanguage}</p>
                </div>
              </div>
            )}

            {duration !== null && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Audio Duration
                </label>
                <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                  <p className="text-gray-800 font-mono">{formatDuration(duration)}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
