import "dotenv/config";
import { GoogleGenAI } from "@google/genai";

console.log("Listing available Gemini models...");

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY
});

async function listModels() {
  try {
    const models = await ai.models.list();
    
    console.log("\nAvailable models:");
    for (const model of models) {
      console.log(`- ${model.name}`);
      if (model.name.includes("image") || model.name.includes("imagen")) {
        console.log(`  ✨ IMAGE MODEL: ${model.name}`);
        console.log(`  Supported methods:`, model.supportedGenerationMethods);
      }
    }
    
  } catch (error) {
    console.error("❌ Error:", error.message);
  }
}

listModels();
