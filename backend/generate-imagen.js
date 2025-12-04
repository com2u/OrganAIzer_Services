// Generate images using Google's Imagen via Generative AI API
import "dotenv/config";
import { GoogleGenerativeAI } from "@google/generative-ai";
import fs from "fs";
import path from "path";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

/**
 * Generate images using Imagen 3
 * @param {string} prompt - Text description for image generation
 * @param {number} numImages - Number of images to generate (1-4)
 * @returns {Promise<Array>} Array of image data URLs
 */
async function generateImages(prompt, numImages = 1) {
  try {
    console.log(`🍌 Generating ${numImages} image(s) with Imagen...`);
    console.log(`Prompt: ${prompt}`);

    // Use Imagen 3 model
    const model = genAI.getGenerativeModel({ model: "imagen-3.0-generate-001" });

    const result = await model.generateContent({
      contents: [{
        role: "user",
        parts: [{
          text: prompt
        }]
      }],
      generationConfig: {
        responseMimeType: "image/png",
        numberOfImages: numImages
      }
    });

    const response = await result.response;
    const images = [];

    // Process generated images
    if (response.candidates && response.candidates.length > 0) {
      for (const candidate of response.candidates) {
        if (candidate.content && candidate.content.parts) {
          for (const part of candidate.content.parts) {
            if (part.inlineData) {
              const base64Data = part.inlineData.data;
              const dataUrl = `data:${part.inlineData.mimeType};base64,${base64Data}`;
              images.push({
                mimeType: part.inlineData.mimeType,
                dataUrl: dataUrl,
                base64: base64Data
              });
            }
          }
        }
      }
    }

    console.log(`✅ Successfully generated ${images.length} image(s)`);
    return images;

  } catch (err) {
    console.error("❌ Error generating images:", err.message);
    console.error("Full error:", err);
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
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const filePaths = [];
  images.forEach((image, index) => {
    const filename = `imagen_${Date.now()}_${index + 1}.png`;
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
    console.log("Usage: node generate-imagen.js <prompt> [numImages]");
    console.log("Example: node generate-imagen.js \"a cute cat\" 2");
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
      model: "imagen-3.0",
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
