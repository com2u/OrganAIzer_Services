import React, { useState } from 'react';

const LLMInteraction: React.FC = () => {
    const [prompt, setPrompt] = useState('');
    const [model, setModel] = useState('google/gemini-2.5-flash');
    const [response, setResponse] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setResponse('');

        try {
            const result = await fetch('http://localhost:8000/api/llm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': 'l5hhroDITUp5zCFEGSaMk43HdVDFlK85'
                },
                body: JSON.stringify({ prompt, model }),
            });

            if (!result.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await result.json();
            setResponse(data.response);
        } catch (error) {
            console.error('Error fetching LLM response:', error);
            setResponse('Failed to get response from the LLM.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="p-4">
            <h2 className="text-2xl font-bold mb-4">LLM Interaction</h2>
            <form onSubmit={handleSubmit}>
                <div className="mb-4">
                    <label htmlFor="prompt" className="block text-gray-700 font-bold mb-2">
                        Prompt
                    </label>
                    <textarea
                        id="prompt"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        className="w-full px-3 py-2 text-gray-700 border rounded-lg focus:outline-none"
                        rows={4}
                    />
                </div>
                <div className="mb-4">
                    <label htmlFor="model" className="block text-gray-700 font-bold mb-2">
                        Model
                    </label>
                    <select
                        id="model"
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        className="w-full px-3 py-2 text-gray-700 border rounded-lg focus:outline-none"
                    >
                        <option value="openrouter/auto">Auto</option>
                        <option value="google/gemini-pro-1.5">Google Gemini Pro 1.5</option>
                        <option value="google/gemini-2.5-flash">Google Gemini 2.5 Flash</option>
                        <option value="openai/gpt-4o">OpenAI GPT-4o</option>
                        <option value="anthropic/claude-3-haiku">Anthropic Claude 3 Haiku</option>
                    </select>
                </div>
                <button
                    type="submit"
                    className="px-4 py-2 font-bold text-white bg-blue-500 rounded-lg hover:bg-blue-700 focus:outline-none"
                    disabled={isLoading}
                >
                    {isLoading ? 'Loading...' : 'Send Prompt'}
                </button>
            </form>
            {response && (
                <div className="mt-4 p-4 border rounded-lg bg-gray-100">
                    <h3 className="text-xl font-bold mb-2">Response</h3>
                    <p>{response}</p>
                </div>
            )}
        </div>
    );
};

export default LLMInteraction;
