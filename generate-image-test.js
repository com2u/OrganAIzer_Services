// generate-image-test.js
// Simple test: call Gemini and print a short text answer

import "dotenv/config";              // loads GEMINI_API_KEY from .env
import { GoogleGenAI } from "@google/genai";

// The client automatically reads process.env.GEMINI_API_KEY
const ai = new GoogleGenAI({});

async function main() {
  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: "Say hello to Renato in one short friendly sentence.",
    });

    // New SDK: response.text is a property, not a function
    console.log("✅ Gemini replied:\n", response.text);
  } catch (err) {
    console.error("❌ Error from Gemini:\n", err);
  }
}

main();
