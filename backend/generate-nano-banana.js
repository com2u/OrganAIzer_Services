// generate-nano-banana.js
// Generate images using Gemini 2.5 Flash Image (aka "nano banana")

import "dotenv/config";
import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY
});

/**
 * Generate images using Gemini 2.5 Flash Image
 * @param {string} prompt - Text description for image generation
 * @param {number} numImages - Number of images to generate (1-4)
 * @returns {Promise<Array>} Array of image data URLs
 */
async function generateImages(prompt, numImages = 1) {
  try {
    console.log(`🍌 Generating ${numImages} image(s) with nano banana...`);
    console.log(`Prompt: ${prompt}`);

    const response = await ai.models.generateImages({
      model: "gemini-2.5-flash-image",
      prompt: prompt,
      config: {
        numberOfImages: numImages,
      },
    });

    const images = [];
    for (const generatedImage of response.generatedImages) {
      const base64Data = generatedImage.image.imageBytes;
      const dataUrl = `data:image/png;base64,${base64Data}`;
      images.push({
        mimeType: "image/png",
        dataUrl: dataUrl,
        base64: base64Data
      });
    }

    console.log(`✅ Successfully generated ${images.length} image(s)`);
    return images;

  } catch (err) {
    console.error("❌ Error generating images:", err.message);
    throw err;
  }
}

/**
 * Save images to disk
 * @param {Array} images - Array of image objects with base64 data
 * @param {string} outputDir - Directory to save images
 * @returns {Array} Array of file paths
 */
function saveImages(images, outputDir = "./data/images") {
  // Create output directory if it doesn't exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const filePaths = [];
  images.forEach((image, index) => {
    const filename = `nano_banana_${Date.now()}_${index + 1}.png`;
    const filepath = path.join(outputDir, filename);
    
    const buffer = Buffer.from(image.base64, "base64");
    fs.writeFileSync(filepath, buffer);
    
    console.log(`💾 Saved: ${filepath}`);
    filePaths.push(filepath);
  });

  return filePaths;
}

// CLI usage
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log("Usage: node generate-nano-banana.js <prompt> [numImages]");
    console.log("Example: node generate-nano-banana.js \"a cute cat\" 2");
    process.exit(1);
  }

  const prompt = args[0];
  const numImages = parseInt(args[1]) || 1;

  try {
    const images = await generateImages(prompt, numImages);
    const filePaths = saveImages(images);
    
    console.log("\n🎉 Generation complete!");
    console.log("Files:", filePaths);
    
    // Return JSON for programmatic use
    const result = {
      success: true,
      model: "gemini-2.5-flash-image",
      prompt: prompt,
      images: images.map((img, idx) => ({
        index: idx + 1,
        mimeType: img.mimeType,
        dataUrl: img.dataUrl,
        filepath: filePaths[idx]
      }))
    };
    
    console.log("\nJSON Output:");
    console.log(JSON.stringify(result, null, 2));
    
  } catch (error) {
    console.error("\n❌ Failed to generate images:", error.message);
    process.exit(1);
  }
}

// Export functions for use as a module
export { generateImages, saveImages };

// Run main if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
