import { GoogleGenAI } from "@google/genai";
import { NextResponse } from "next/server";
import { z } from "zod";

// Zod Schema for validation
const requestSchema = z.object({
  image: z.string().regex(/^data:image\/(png|jpeg|webp);base64,/, {
    message: "Image must be a valid base64 data URI (PNG, JPEG, or WEBP)",
  }),
});

// Simple In-memory Rate Limiter
interface RateLimitInfo {
  count: number;
  resetTime: number;
}
const rateLimitMap = new Map<string, RateLimitInfo>();
const LIMIT_WINDOW_MS = 60 * 1000; // 1 minute
const MAX_REQUESTS = 20; // Max 20 requests per minute

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const info = rateLimitMap.get(ip);

  if (!info) {
    rateLimitMap.set(ip, { count: 1, resetTime: now + LIMIT_WINDOW_MS });
    return false;
  }

  if (now > info.resetTime) {
    info.count = 1;
    info.resetTime = now + LIMIT_WINDOW_MS;
    return false;
  }

  info.count += 1;
  return info.count > MAX_REQUESTS;
}

// Fallback high-fidelity architectural 3D primitives (Demo mode when API key is not configured)
const DEMO_3D_PRIMITIVES = [
  {
    type: "box",
    name: "LDK (Living & Dining)",
    position: [0, 0.1, 0],
    size: [6, 0.2, 4],
    color: "#e0e7ff",
  },
  {
    type: "box",
    name: "Master Bedroom",
    position: [4.5, 0.1, 0],
    size: [3, 0.2, 4],
    color: "#fef3c7",
  },
  {
    type: "box",
    name: "Sanitary & Bath (UB)",
    position: [-4, 0.1, 1],
    size: [2, 0.2, 2],
    color: "#cffafe",
  },
  {
    type: "box",
    name: "North Exterior Wall",
    position: [0, 1.2, -2],
    size: [12, 2.4, 0.2],
    color: "#64748b",
  },
  {
    type: "box",
    name: "South Exterior Wall",
    position: [0, 1.2, 2],
    size: [12, 2.4, 0.2],
    color: "#64748b",
  },
  {
    type: "box",
    name: "West Partition Wall",
    position: [-3, 1.2, 0],
    size: [0.2, 2.4, 4],
    color: "#94a3b8",
  },
  {
    type: "box",
    name: "East Partition Wall",
    position: [3, 1.2, 0],
    size: [0.2, 2.4, 4],
    color: "#94a3b8",
  },
  {
    type: "cylinder",
    name: "Structural Column (RC)",
    position: [3, 1.2, 2],
    size: [0.3, 2.4, 16],
    color: "#334155",
  },
];

export async function POST(req: Request) {
  // Rate Limiting
  const ip = req.headers.get("x-forwarded-for") || req.headers.get("x-real-ip") || "127.0.0.1";
  if (isRateLimited(ip)) {
    return NextResponse.json(
      { error: "Too many requests. Please try again after 1 minute." },
      { status: 429 }
    );
  }

  try {
    const body = await req.json();

    // Zod Validation
    const validation = requestSchema.safeParse(body);
    if (!validation.success) {
      return NextResponse.json(
        { error: validation.error.issues[0].message },
        { status: 400 }
      );
    }

    const { image } = validation.data;

    // Graceful fallback to demo primitives if GEMINI_API_KEY is not set
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      console.warn("GEMINI_API_KEY is not set. Providing demo 3D model fallback.");
      return NextResponse.json(DEMO_3D_PRIMITIVES, {
        headers: { "x-demo-fallback": "true" },
      });
    }

    const ai = new GoogleGenAI({ apiKey });

    // Remove base64 prefix
    const base64Data = image.split(",")[1];

    const prompt = `
      Analyze this 2D CAD floorplan sketch and convert it into a set of 3D structural primitives for React Three Fiber rendering.
      Ensure all bounding rooms and structural walls have accurate scale and coordinates.
    `;

    // Strict Structured Outputs Schema for Type-Safe 3D Primitives
    const responseSchema = {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: {
          type: {
            type: "STRING",
            enum: ["box", "cylinder", "sphere"],
            description: "Primitive 3D mesh type",
          },
          position: {
            type: "ARRAY",
            items: { type: "NUMBER" },
            description: "[x, y, z] coordinates in 3D scene",
          },
          size: {
            type: "ARRAY",
            items: { type: "NUMBER" },
            description: "[width, height, depth] or [radius, height, ...]",
          },
          color: {
            type: "STRING",
            description: "Hex color code e.g. #4f46e5",
          },
          name: {
            type: "STRING",
            description: "Descriptive name of the room or structural element",
          },
        },
        required: ["type", "position", "size", "color", "name"],
      },
    };

    const result = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: [
        {
          role: "user",
          parts: [
            { text: prompt },
            {
              inlineData: {
                data: base64Data,
                mimeType: "image/png",
              },
            },
          ],
        },
      ],
      config: {
        responseMimeType: "application/json",
        responseSchema,
      },
    });

    const responseText = result.text ?? "[]";
    try {
      const parsedData = JSON.parse(responseText);
      return NextResponse.json(parsedData);
    } catch {
      console.error("Failed to parse Gemini Structured Output JSON:", responseText);
      return NextResponse.json(DEMO_3D_PRIMITIVES, {
        headers: { "x-demo-fallback": "parse_error" },
      });
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("Gemini API Error:", error);
    // Return demo model fallback instead of 500 error on AI API transient failure
    return NextResponse.json(DEMO_3D_PRIMITIVES, {
      headers: { "x-demo-fallback": "api_error", "x-error-message": message },
    });
  }
}
