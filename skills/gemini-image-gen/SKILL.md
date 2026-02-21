---
name: gemini-image-gen
description: "Generate or edit images with Google Gemini. Alternative to DALL-E for image generation. Requires GEMINI_API_KEY."
requires_env:
  - GEMINI_API_KEY
---

# Gemini Image Generation

Generate images using Google's Gemini model.

## When to Use

- User asks for image generation and DALL-E is not available
- User specifically requests Gemini
- Image editing with text instructions

## Generate an Image

```bash
curl -s -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "Generate an image of: detailed description here"}]}],
    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
  }'
```

## Response

Response contains `candidates[0].content.parts[]`. Image data appears in parts with:
- `inlineData.mimeType` (e.g., `image/png`)
- `inlineData.data` (base64-encoded)

Save to file:
```bash
echo "BASE64_DATA" | base64 -d > image.png
```

## Notes

- Free tier available with rate limits
- Model availability may vary — check Google AI Studio
- Supports both generation and editing via text prompts
