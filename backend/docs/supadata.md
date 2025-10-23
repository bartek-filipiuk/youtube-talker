Auth or use SDK

Base url: https://api.supadata.ai/v1

curl -H "x-api-key: YOUR_API_KEY" https://api.supadata.ai/v1/

SDK:

pip install supadata

from supadata import Supadata, SupadataError

# Initialize the client
supadata = Supadata(api_key="YOUR_API_KEY")

video = supadata.youtube.video(id="https://youtu.be/dQw4w9WgXcQ") # can be url or video id
print(f"Video: {video}")

example:

1. Video Metadata

from supadata import Supadata, SupadataError

# Initialize the client
supadata = Supadata(api_key="YOUR_API_KEY")

video = supadata.youtube.video(id="https://youtu.be/dQw4w9WgXcQ") # can be url or video id
print(f"Video: {video}")

RESPONSE:

{
  "id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "description": "The official music video for \"Never Gonna Give You Up\"...",
  "duration": 213,
  "channel": {
    "id": "UCuAXFkgsw1L7xaCfnd5JJOw",
    "name": "Rick Astley"
  },
  "tags": ["Rick Astley", "Official Video", "Music"],
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
  "uploadDate": "2009-10-25T00:00:00.000Z",
  "viewCount": 1234567890,
  "likeCount": 12345678,
  "transcriptLanguages": ["en", "es", "fr"]
}

2. Transcript

from supadata import Supadata, SupadataError

# Initialize the client
supadata = Supadata(api_key="YOUR_API_KEY")

text_transcript = supadata.youtube.transcript(
    video_id="dQw4w9WgXcQ",
    text=True
)
print(text_transcript.content)

Response

{
  "content": "Never gonna give you up, never gonna let you down...",
  "lang": "en",
  "availableLangs": ["en", "es", "zh-TW"]
}



