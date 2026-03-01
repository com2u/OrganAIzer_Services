/**
 * Video Transcription page component.
 * Interface for transcribing videos from YouTube URLs, generic video URLs, or uploaded files.
 */

import { useState, useRef } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import { transcribeVideo } from '../lib/api';

type SourceType = 'youtube' | 'url' | 'upload';

export default function YouTubePage() {
  const [sourceType, setSourceType] = useState<SourceType>('youtube');
  const [url, setUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [transcript, setTranscript] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [qualityMode, setQualityMode] = useState<'fast' | 'accurate'>('accurate');
  const [languagePreference, setLanguagePreference] = useState<string>('auto');
  const fileInputRef = useRef<HTMLInputElement>(null);

  /**
   * Validates if the input is a valid YouTube URL.
   */
  const isValidYouTubeUrl = (url: string): boolean => {
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname.toLowerCase();
      
      return (
        hostname === 'www.youtube.com' ||
        hostname === 'youtube.com' ||
        hostname === 'youtu.be' ||
        hostname === 'm.youtube.com'
      );
    } catch {
      return false;
    }
  };

  /**
   * Validates if the input is a valid URL.
   */
  const isValidUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  /**
   * Handles file selection from the file input.
   */
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      const allowedExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'];
      const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
      
      if (!allowedExtensions.includes(fileExtension)) {
        setError('Please select a valid video file (MP4, MOV, AVI, MKV, WEBM, FLV, WMV)');
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      // Validate file size (500MB max)
      const maxSizeMB = 500;
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
    // Validation based on source type
    if (sourceType === 'youtube' || sourceType === 'url') {
      if (!url.trim()) {
        setError(`Please enter a ${sourceType === 'youtube' ? 'YouTube' : 'video'} URL.`);
        return;
      }

      // Validate URL format
      if (sourceType === 'youtube' && !isValidYouTubeUrl(url.trim())) {
        setError('Please enter a valid YouTube URL.');
        return;
      }

      if (sourceType === 'url' && !isValidUrl(url.trim())) {
        setError('Please enter a valid video URL.');
        return;
      }
    } else if (sourceType === 'upload') {
      if (!selectedFile) {
        setError('Please select a video file.');
        return;
      }
    }

    // Clear previous results and errors
    setError('');
    setTranscript('');
    setIsLoading(true);

    try {
      const response = await transcribeVideo(
        sourceType,
        url.trim() || undefined,
        languagePreference,
        qualityMode,
        selectedFile || undefined
      );

      setTranscript(response.transcript || '');
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
      console.error('Video transcription error:', err);
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
      alert('Transcript copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      setError('Failed to copy to clipboard');
    }
  };

  /**
   * Handles Enter key press in the input field.
   */
  const handleKeyPress = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !isLoading) {
      handleTranscribe();
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

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h2 className="text-3xl font-bold mb-6 text-gray-800">Video → Text</h2>
      
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <div className="bg-white shadow-md rounded-lg p-6">
        {/* Source Type Selector */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Video Source
          </label>
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={() => {
                setSourceType('youtube');
                setUrl('');
                setSelectedFile(null);
                setError('');
              }}
              disabled={isLoading}
              className={`px-4 py-3 rounded-md font-medium transition-colors ${
                sourceType === 'youtube'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              YouTube URL
            </button>
            <button
              onClick={() => {
                setSourceType('url');
                setUrl('');
                setSelectedFile(null);
                setError('');
              }}
              disabled={isLoading}
              className={`px-4 py-3 rounded-md font-medium transition-colors ${
                sourceType === 'url'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              Video URL
            </button>
            <button
              onClick={() => {
                setSourceType('upload');
                setUrl('');
                setSelectedFile(null);
                setError('');
              }}
              disabled={isLoading}
              className={`px-4 py-3 rounded-md font-medium transition-colors ${
                sourceType === 'upload'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              Upload File
            </button>
          </div>
        </div>

        {/* YouTube URL Input  */}
        {sourceType === 'youtube' && (
          <div className="mb-6">
            <label htmlFor="youtube-url" className="block text-sm font-medium text-gray-700 mb-2">
              YouTube URL
            </label>
            <input
              id="youtube-url"
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              className="block w-full px-4 py-3 text-sm border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <p className="mt-2 text-sm text-gray-500">
              Paste a YouTube video URL to transcribe its audio content
            </p>
          </div>
        )}

        {/* Generic Video URL Input */}
        {sourceType === 'url' && (
          <div className="mb-6">
            <label htmlFor="video-url" className="block text-sm font-medium text-gray-700 mb-2">
              Video URL
            </label>
            <input
              id="video-url"
              type="url"
              placeholder="https://example.com/video.mp4"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              className="block w-full px-4 py-3 text-sm border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <p className="mt-2 text-sm text-gray-500">
              Paste a direct link to a video file (MP4, MOV, etc.)
            </p>
          </div>
        )}

        {/* File Upload Input */}
        {sourceType === 'upload' && (
          <div className="mb-6">
            <label htmlFor="video-file" className="block text-sm font-medium text-gray-700 mb-2">
              Upload Video File
            </label>
            <input
              id="video-file"
              ref={fileInputRef}
              type="file"
              accept=".mp4,.mov,.avi,.mkv,.webm,.flv,.wmv,video/*"
              onChange={handleFileChange}
              disabled={isLoading}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <p className="mt-2 text-sm text-gray-500">
              Supported formats: MP4, MOV, AVI, MKV, WEBM, FLV, WMV (max 500MB)
            </p>
            
            {selectedFile && (
              <div className="mt-4 p-4 bg-gray-50 rounded-md border border-gray-200">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Selected File</h3>
                <div className="text-sm text-gray-600">
                  <p><span className="font-medium">Name:</span> {selectedFile.name}</p>
                  <p><span className="font-medium">Size:</span> {formatFileSize(selectedFile.size)}</p>
                  <p><span className="font-medium">Type:</span> {selectedFile.type || 'Unknown'}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Language Preference */}
        <div className="mb-6">
          <label htmlFor="language-select" className="block text-sm font-medium text-gray-700 mb-2">
            Language (for better accuracy)
          </label>
          <select
            id="language-select"
            value={languagePreference}
            onChange={(e) => setLanguagePreference(e.target.value)}
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
        </div>

        {/* Quality Mode */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Quality Mode
          </label>
          <div className="flex gap-4">
            <label className="flex items-center cursor-pointer">
              <input
                type="radio"
                name="quality-mode"
                value="accurate"
                checked={qualityMode === 'accurate'}
                onChange={(e) => setQualityMode(e.target.value as 'fast' | 'accurate')}
                disabled={isLoading}
                className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:opacity-50"
              />
              <span className="ml-2 text-sm">
                <span className="font-medium text-gray-900">Accurate</span>
                <span className="text-gray-500"> - Higher quality (slower, recommended)</span>
              </span>
            </label>
            <label className="flex items-center cursor-pointer">
              <input
                type="radio"
                name="quality-mode"
                value="fast"
                checked={qualityMode === 'fast'}
                onChange={(e) => setQualityMode(e.target.value as 'fast' | 'accurate')}
                disabled={isLoading}
                className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:opacity-50"
              />
              <span className="ml-2 text-sm">
                <span className="font-medium text-gray-900">Fast</span>
                <span className="text-gray-500"> - Lower quality (faster)</span>
              </span>
            </label>
          </div>
        </div>

        <button
          onClick={handleTranscribe}
          disabled={
            isLoading ||
            (sourceType !== 'upload' && !url.trim()) ||
            (sourceType === 'upload' && !selectedFile)
          }
          className={`w-full py-3 px-4 rounded-md font-medium text-white transition-colors ${
            isLoading ||
            (sourceType !== 'upload' && !url.trim()) ||
            (sourceType === 'upload' && !selectedFile)
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          {isLoading ? 'Transcribing... (this may take a while)' : 'Transcribe Video'}
        </button>

        {isLoading && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-center">
              <svg className="animate-spin h-5 w-5 mr-3 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <p className="text-sm text-blue-800">
                Processing video and transcribing audio... This may take several minutes for long videos.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Results section */}
      {transcript && (
        <div className="mt-8 bg-white shadow-md rounded-lg p-6">
          <h3 className="text-xl font-semibold mb-4 text-gray-800">Transcript</h3>
          
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Transcribed Text
              </label>
              <button
                onClick={handleCopyToClipboard}
                className="px-3 py-1 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
              >
                Copy to Clipboard
              </button>
            </div>
            <textarea
              className="w-full h-96 p-4 border border-gray-300 rounded-md bg-gray-50 text-gray-800 whitespace-pre-wrap font-normal resize-y"
              value={transcript}
              readOnly
            />
          </div>
        </div>
      )}
    </div>
  );
}
