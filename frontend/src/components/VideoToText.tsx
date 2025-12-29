import { useState } from 'react';

const VideoToText = () => {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ text: string; language: string; segments: any[] } | null>(null);

  const handleTranscribe = async () => {
    if (!file && !url) {
      setError('Please select a file or enter a YouTube URL');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      if (file) {
        formData.append('file', file);
      } else {
        formData.append('video_url', url);
      }
      const response = await fetch('/api/video-text/transcribe', {
        method: 'POST',
        headers: {
            'X-API-Key': 'l5hhroDITUp5zCFEGSaMk43HdVDFlK85'
        },
        body: formData,
      });
      if (!response.ok) {
        throw new Error('Transcription failed');
      }
      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">Video to Text</h2>
      <input
        type="file"
        accept="video/*"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        className="w-full p-2 border border-gray-300 rounded mb-4"
      />
      <p className="text-center mb-4">or</p>
      <input
        type="text"
        placeholder="Enter YouTube URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        className="w-full p-2 border border-gray-300 rounded mb-4"
      />
      <button
        onClick={handleTranscribe}
        disabled={loading}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 mb-4"
      >
        {loading ? 'Transcribing...' : 'Generate Transcript'}
      </button>
      {result && (
        <div className="mb-4">
          <p><strong>Transcript:</strong> {result.text}</p>
          <p><strong>Language:</strong> {result.language}</p>
        </div>
      )}
      {error && <p className="text-red-500 mt-2">{error}</p>}
    </div>
  );
};

export default VideoToText;
