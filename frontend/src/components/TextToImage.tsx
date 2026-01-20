import { useState } from 'react';

type AspectRatio = 'square' | 'landscape' | 'portrait' | 'wide' | 'tall';

interface AspectRatioOption {
  value: AspectRatio;
  label: string;
  icon: string;
  dimensions: string;
}

const ASPECT_RATIO_OPTIONS: AspectRatioOption[] = [
  { value: 'square', label: 'Square', icon: '⬜', dimensions: '1:1' },
  { value: 'landscape', label: 'Landscape', icon: '🖼️', dimensions: '3:2' },
  { value: 'portrait', label: 'Portrait', icon: '📱', dimensions: '2:3' },
  { value: 'wide', label: 'Wide', icon: '🎬', dimensions: '16:9' },
  { value: 'tall', label: 'Tall', icon: '📜', dimensions: '9:16' },
];

const TextToImage = () => {
  const [prompt, setPrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('square');
  const [uploadedImages, setUploadedImages] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [images, setImages] = useState<{ url: string; id: string; description?: string }[]>([]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setUploadedImages(files);
  };

  const handleGenerate = async () => {
    if (!prompt) {
      setError('Please enter a prompt');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('prompt', prompt);
      formData.append('aspect_ratio', aspectRatio);

      // Add uploaded images if any
      uploadedImages.forEach((file) => {
        formData.append('images', file);
      });

      const response = await fetch('/api/text-image/generate', {
        method: 'POST',
        headers: {
            'X-API-Key': import.meta.env.VITE_API_KEY
        },
        body: formData,
      });
      if (!response.ok) {
        throw new Error('Generation failed');
      }
      const data = await response.json();
      setImages(data.images);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (imageUrl: string, filename: string) => {
    try {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-white p-8 rounded-xl shadow-lg border border-gray-200">
      <div className="flex items-center mb-6">
        <div className="bg-purple-500 p-3 rounded-full mr-4">
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-gray-800">Text to Image Generator</h2>
      </div>

      <p className="text-gray-600 mb-6">Generate images from text prompts using AI. Optionally upload reference images for better results.</p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Image Prompt</label>
          <textarea
            placeholder="Describe the image you want to generate..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Aspect Ratio</label>
          <div className="grid grid-cols-5 gap-2">
            {ASPECT_RATIO_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setAspectRatio(option.value)}
                className={`p-3 rounded-lg border-2 transition-all flex flex-col items-center justify-center ${
                  aspectRatio === option.value
                    ? 'border-purple-500 bg-purple-50 text-purple-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="text-xl mb-1">{option.icon}</span>
                <span className="text-xs font-medium">{option.label}</span>
                <span className="text-xs text-gray-400">{option.dimensions}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Reference Images (Optional)</label>
          <input
            type="file"
            multiple
            accept="image/*"
            onChange={handleImageUpload}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
          />
          {uploadedImages.length > 0 && (
            <p className="text-sm text-gray-600 mt-2">
              {uploadedImages.length} image{uploadedImages.length > 1 ? 's' : ''} selected
            </p>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="w-full bg-purple-600 text-white py-3 px-6 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 transition-colors"
        >
          {loading ? (
            <>
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Generating Images...</span>
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span>Generate Images</span>
            </>
          )}
        </button>

        {images.length > 0 && (
          <div className="mt-8">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Generated Images</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {images.map((img, index) => (
                <div key={img.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <img
                    src={img.url}
                    alt={`Generated image ${index + 1}`}
                    className="w-full h-64 object-cover rounded-lg mb-4"
                  />
                  {img.description && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
                      <p className="text-sm text-blue-800">
                        <strong>AI Description:</strong> {img.description}
                      </p>
                      <p className="text-xs text-blue-600 mt-1">
                        Note: This shows what a real image generation API would create based on the Gemini AI description.
                      </p>
                    </div>
                  )}
                  <button
                    onClick={() => handleDownload(img.url, `generated-image-${index + 1}.png`)}
                    className="w-full bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center space-x-2"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span>Download</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-800">{error}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TextToImage;
