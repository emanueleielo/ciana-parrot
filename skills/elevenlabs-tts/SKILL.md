---
name: elevenlabs-tts
description: "Text-to-speech with ElevenLabs: generate realistic voice audio from text. Requires ELEVENLABS_API_KEY."
requires_env:
  - ELEVENLABS_API_KEY
---

# ElevenLabs Text-to-Speech

Generate realistic voice audio from text.

## When to Use

- "Read this aloud"
- "Generate audio of this text"
- "Create a voice message"
- Any text-to-speech request

## List Available Voices

```bash
curl -s "https://api.elevenlabs.io/v1/voices" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" | jq '.voices[] | {name: .name, voice_id: .voice_id}'
```

## Generate Speech

```bash
curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  --output speech.mp3 \
  -d '{
    "text": "Text to convert to speech",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
      "stability": 0.5,
      "similarity_boost": 0.75
    }
  }'
```

## Default Voice IDs

- `21m00Tcm4TlvDq8ikWAM` — Rachel (female, calm)
- `EXAVITQu4vr4xnSDxMaL` — Bella (female, warm)
- `ErXwobaYiN019PkySvjV` — Antoni (male, articulate)

Use the List Voices endpoint to find all available voices.

## Models

- `eleven_multilingual_v2` — Best quality, 29 languages
- `eleven_monolingual_v1` — English only, fast
- `eleven_turbo_v2` — Lowest latency

## Notes

- Free tier: 10,000 characters/month
- Output: mp3
- After generating, deliver the audio file to the user
