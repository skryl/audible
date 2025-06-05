#!/bin/bash

# Test Gemini TTS API with curl
echo "Testing Gemini TTS API..."

# Get the API key from environment
API_KEY=""

if [ -z "$API_KEY" ]; then
    echo "Error: No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY"
    exit 1
fi

echo "Using API key: ${API_KEY:0:10}...${API_KEY: -4}"

# Make the TTS request
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -X POST \
  -d '{
    "contents": [
      {
        "parts": [
          {
            "text": "Hello, this is a test of the Gemini text to speech API."
          }
        ]
      }
    ],
    "generationConfig": {
      "response_modalities": ["AUDIO"],
      "speechConfig": {
        "voiceConfig": {
          "prebuiltVoiceConfig": {
            "voiceName": "Charon"
          }
        }
      }
    }
  }' \
  -o test_audio_response.json

echo ""
echo "Response saved to test_audio_response.json"
echo ""
echo "Checking response status..."
if grep -q '"error"' test_audio_response.json 2>/dev/null; then
    echo "Error in response:"
    cat test_audio_response.json | python3 -m json.tool
else
    echo "Success! Audio data received."
    echo "Response size: $(wc -c < test_audio_response.json) bytes"
fi