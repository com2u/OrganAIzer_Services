import "dotenv/config";
import { GoogleGenAI } from "@google/genai";

console.log("Testing Nano Banana (Gemini 2.5 Flash Image)...");
console.log("API Key present:", !!process.env.GEMINI_API_KEY);
console.log("API Key starts with:", process.env.GEMINI_API_KEY?.substring(0, 10));

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY
});

async function test() {
  try {
    console.log("\nAttempting to generate image...");
    
    const response = await ai.models.generateImages({
      model: "gemini-2.5-flash-image",
      prompt: "a simple red circle",
      config: {
        numberOfImages: 1,
      },
    });

    console.log("✅ Success! Generated", response.generatedImages?.length, "image(s)");
    console.log("Response keys:", Object.keys(response));
    
  } catch (error) {
    console.error("❌ Error:", error.message);
    console.error("Error details:", error);
    process.exit(1);
  }
}

test();
