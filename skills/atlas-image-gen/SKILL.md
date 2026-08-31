---
name: atlas-image-gen
description: "Generate images with Atlas Cloud text-to-image models. Use when the user asks to create or generate an image with Atlas Cloud. Requires ATLASCLOUD_API_KEY."
requires_env:
  - ATLASCLOUD_API_KEY
---

# Atlas Cloud Image Generation

Generate images through Atlas Cloud without changing the existing OpenAI or Gemini image skills.

## When to Use

- The user explicitly requests Atlas Cloud
- The user wants an Atlas Cloud text-to-image model
- `ATLASCLOUD_API_KEY` is configured

## Tool

Call `generate_atlas_image` with a detailed prompt. The default model is `black-forest-labs/flux-schnell` and the default size is `1024*1024`.

Optional arguments:

- `model`: exact Atlas Cloud text-to-image model ID
- `size`: model-supported output size, such as `1024*1024`

## Workflow

1. Turn the request into a detailed image prompt.
2. Call `generate_atlas_image` once for each image the user requested.
3. Share the returned output URL.
4. Download the URL when the user needs a durable local copy.

## Notes

- Image generation is billable. The tool never retries the generation POST.
- Prediction GET requests use bounded polling and transient-error backoff.
- Model parameters vary. Use a model-compatible size when overriding the defaults.
