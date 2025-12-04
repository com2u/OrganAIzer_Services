import "dotenv/config";
import { GoogleGenerativeAI } from "@google/generative-ai";
import fs from "fs";
import path from "path";

async function generateImage() {
  try {
    // Validate API key
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error("GEMINI_API_KEY is not set in environment variables");
    }

    console.log("Initializing Google Generative AI...");
    const genAI = new GoogleGenerativeAI(apiKey);

    // Get the image generation model
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash-image" });

    // Generate image from text prompt
    const prompt = "A serene mountain landscape at sunset with a lake";
    console.log(`Generating image for prompt: "${prompt}"`);

    const result = await model.generateContent(prompt);
    const response = await result.response;

    // Get the generated image data
    if (response.candidates && response.candidates[0].content.parts) {
      const imagePart = response.candidates[0].content.parts.find(
        (part) => part.inlineData && part.inlineData.mimeType.startsWith("image/")
      );

      if (imagePart && imagePart.inlineData) {
        // Decode base64 image data
        const imageData = Buffer.from(imagePart.inlineData.data, "base64");

        // Save to file
        const outputPath = path.join(process.cwd(), "generated_image.png");
        fs.writeFileSync(outputPath, imageData);

        console.log(`✓ Image generated successfully!`);
        console.log(`✓ Saved to: ${outputPath}`);
      } else {
        throw new Error("No image data found in response");
      }
    } else {
      throw new Error("Unexpected response format");
    }
  } catch (error) {
    console.error("✗ Error generating image:", error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// Run the function
generateImage();
