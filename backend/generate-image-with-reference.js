import "dotenv/config";
import { GoogleGenerativeAI } from "@google/generative-ai";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function generateImageWithReference() {
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

    // Read reference image
    const referencePath = path.join(__dirname, "reference.png");
    if (!fs.existsSync(referencePath)) {
      throw new Error(`Reference image not found at: ${referencePath}`);
    }

    console.log(`Reading reference image from: ${referencePath}`);
    const referenceImageData = fs.readFileSync(referencePath);
    const referenceImageBase64 = referenceImageData.toString("base64");

    // Generate image using reference and prompt
    const prompt = "Create a similar image with enhanced colors and lighting";
    console.log(`Generating image with prompt: "${prompt}"`);

    const result = await model.generateContent([
      {
        inlineData: {
          data: referenceImageBase64,
          mimeType: "image/png",
        },
      },
      prompt,
    ]);

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
        const outputPath = path.join(__dirname, "generated_from_reference.png");
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
generateImageWithReference();
