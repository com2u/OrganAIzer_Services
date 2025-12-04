import "dotenv/config";
import { GoogleGenAI } from "@google/genai";
import fs from "fs";

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

async function main() {
  try {
    const prompt = "A cat dressed like a superhero";

    // Load a reference image from your PC (put an image into the project folder)
    const referenceImage = fs.readFileSync("./reference.jpg");
    const base64Image = referenceImage.toString("base64");

    const response = await ai.models.generateContent({
      model: "gemini-2.0-flash-lite",
      contents: [
        {
          role: "user",
          parts: [
            { text: prompt },
            {
              inlineData: {
                mimeType: "image/jpeg",
                data: base64Image,
              },
            },
          ],
        },
      ],
      output: "image",
    });

    // Save output
    const imageData = response.data;
    const buffer = Buffer.from(imageData, "base64");
    fs.writeFileSync("generated_from_reference.png", buffer);

    console.log("Image with reference saved as generated_from_reference.png");
  } catch (error) {
    console.error("Error:", error);
  }
}

main();
