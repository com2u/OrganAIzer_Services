import { useState } from 'react';
import ErrorBanner from '../components/ErrorBanner';
import { generateImages } from '../lib/api';

interface GeneratedImage {
  url: string;
  prompt: string;
}

export default function ImageGenPage() {
  const [prompt, setPrompt] = useState('');
  const [numImages, setNumImages] = useState(1);
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImage[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setGeneratedImages([]);

    try {
      const result = await generateImages({
        prompt: prompt.trim(),
        num_images: numImages,
        aspect_ratio: aspectRatio,
      });

      const images = result.images.map((url: string) => ({
        url: `http://localhost:8000${url}`,
        prompt: result.prompt,
      }));

      setGeneratedImages(images);
    } catch (err: any) {
      console.error('Image generation error:', err);
      setError(err.message || 'Failed to generate images. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = (imageUrl: string, index: number) => {
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = `generated-image-${index + 1}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            AI Image Generation
          </h1>
          <p className="text-gray-600">
            Create stunning images from text descriptions using Google Vertex AI Imagen
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-xl p-6 mb-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="prompt" className="block text-sm font-medium text-gray-700 mb-2">
                Image Description (Prompt)
              </label>
              <textarea
                id="prompt"
                rows={4}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                placeholder="Describe the image you want to create... (e.g., 'A serene mountain landscape at sunset with a lake')"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={isGenerating}
              />
              <p className="mt-1 text-sm text-gray-500">
                Be specific and descriptive for best results
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="numImages" className="block text-sm font-medium text-gray-700 mb-2">
                  Number of Images
                </label>
                <select
                  id="numImages"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  value={numImages}
                  onChange={(e) => setNumImages(Number(e.target.value))}
                  disabled={isGenerating}
                >
                  <option value={1}>1 image</option>
                  <option value={2}>2 images</option>
                  <option value={3}>3 images</option>
                  <option value={4}>4 images</option>
                </select>
              </div>

              <div>
                <label htmlFor="aspectRatio" className="block text-sm font-medium text-gray-700 mb-2">
                  Aspect Ratio
                </label>
                <select
                  id="aspectRatio"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(e.target.value)}
                  disabled={isGenerating}
                >
                  <option value="1:1">1:1 (Square)</option>
                  <option value="16:9">16:9 (Landscape)</option>
                  <option value="9:16">9:16 (Portrait)</option>
                  <option value="4:3">4:3 (Traditional)</option>
                  <option value="3:4">3:4 (Portrait)</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isGenerating || !prompt.trim()}
              className="w-full bg-purple-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {isGenerating ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Generating Images...
                </span>
              ) : (
                'Generate Images'
              )}
            </button>
          </form>
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        {generatedImages.length > 0 && (
          <div className="bg-white rounded-lg shadow-xl p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">
              Generated Images
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {generatedImages.map((image, index) => (
                <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
                  <img
                    src={image.url}
                    alt={`Generated: ${image.prompt}`}
                    className="w-full h-auto"
                  />
                  <div className="p-4 bg-gray-50">
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {image.prompt}
                    </p>
                    <button
                      onClick={() => handleDownload(image.url, index)}
                      className="w-full bg-purple-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition-colors"
                    >
                      Download Image
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-900 mb-2">💡 Tips for Better Results</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Be specific and descriptive in your prompts</li>
            <li>Include details about style, lighting, and mood</li>
            <li>Mention specific artistic styles or techniques if desired</li>
            <li>Describe the composition and key elements</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
