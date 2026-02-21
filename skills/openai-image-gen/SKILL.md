---
name: openai-image-gen
description: "Generate images with DALL-E 3 via OpenAI API. Use when user asks to create or generate images. Requires OPENAI_API_KEY."
requires_env:
  - OPENAI_API_KEY
---

# OpenAI Image Generation

Generate images using DALL-E 3.

## When to Use

- "Generate an image of..."
- "Create a picture of..."
- "Draw me a..."
- "Make an illustration for..."

## Generate an Image

```bash
curl -s -X POST "https://api.openai.com/v1/images/generations" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dall-e-3",
    "prompt": "A detailed description of the image...",
    "size": "1024x1024",
    "quality": "standard",
    "n": 1
  }'
```

## Options

### Sizes
- `1024x1024` — Square (default)
- `1792x1024` — Landscape
- `1024x1792` — Portrait

### Quality
- `standard` — Faster, cheaper (~$0.04)
- `hd` — More detail (~$0.08)

## Response

Returns JSON with `data[0].url` (temporary, expires in 1 hour) and `data[0].revised_prompt`.

## Workflow

1. Craft a detailed prompt from user's request
2. Generate via API
3. Extract URL from `data[0].url`
4. Share URL with user
5. Optionally save: `curl -s -o image.png "GENERATED_URL"`

## Prompt Tips

- Be specific: style, composition, lighting, colors
- Include medium: photorealistic, watercolor, 3D render, pixel art
- Mention what should NOT appear if important

## Notes

- URLs expire after 1 hour — download to keep
- Content policy applies — some prompts may be refused
- DALL-E 3 may revise your prompt (check `revised_prompt` in response)
