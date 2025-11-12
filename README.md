# Qivio

**Learn from YouTube videos efficiently with AI-powered chat.**

Qivio is an intelligent chat application that lets you have conversations with YouTube video content. Upload any video to ask questions, get summaries, or explore topics in-depth. Join curated channels to learn from collections of related videos.

Built with FastAPI, Astro, and vector search for fast, accurate responses.

---

## Quick Start

### Prerequisites

- Docker (for PostgreSQL + Qdrant)
- Python 3.11+
- Node.js 18+
- API keys for:
  - [OpenRouter](https://openrouter.ai) (LLM completions)
  - [OpenAI](https://platform.openai.com) (embeddings)
  - [SUPADATA](https://supadata.ai) (YouTube transcription)

### Installation

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd talkt-to-youtube

   # Copy environment files
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env

   # Add your API keys to backend/.env
   ```

2. **Start the application:**
   ```bash
   ./dev.sh
   ```

   This single command will:
   - Start PostgreSQL and Qdrant (Docker)
   - Run database migrations
   - Start the backend API (port 8000)
   - Start the frontend (port 4321)

3. **Access the application:**
   - Frontend: http://localhost:4321
   - API Docs: http://localhost:8000/docs

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md).

---

## How to Use

### Personal Chat - Load & Talk with Videos

1. **Register/Login** at http://localhost:4321
2. **Open Chat** - Click "Chat" in the navigation
3. **Add a video:**
   - Paste a YouTube URL in the chat input
   - System detects the URL and asks for confirmation
   - Reply "yes" to load the video (transcription + indexing)
4. **Ask questions** about the video content
5. **Manage videos** in the sidebar - view, select, or delete your videos

**Example:**
```
You: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Bot: Found video "Example Video Title". Add to your library? Reply with 'yes' or 'no'
You: yes
Bot: ✓ Video loaded successfully! You can now ask questions about it.
You: What are the main topics covered in this video?
```

### Channels - Explore Curated Collections

1. **Browse Channels** - Navigate to "Channels" page
2. **Select a channel** - View channels organized by topic
3. **Join channel chat** - Click on a channel to start chatting
4. **Ask questions** about any video in the channel's collection

Channels are curated collections of related videos, perfect for learning about specific topics.

---

## Key Features

- **Real-time AI Chat**: WebSocket-based responses
- **Multi-Model Support**: Choose from Claude 4.5 Haiku, Gemini 2.5 Flash, and more
- **Smart Video Search**: Vector search finds relevant moments in videos
- **Conversation History**: Save and manage multiple conversations
- **Two Chat Modes**:
  - Personal: Upload any YouTube video on-demand
  - Channels: Pre-curated video collections for focused learning

---

## Architecture

### Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- PostgreSQL (relational data: users, conversations, metadata)
- Qdrant (vector database for semantic search)
- LangChain/LangGraph (RAG orchestration)

**Frontend:**
- Astro (static site framework)
- TailwindCSS (styling)
- Nanostores (state management)
- WebSockets (real-time communication)

**AI/ML:**
- OpenRouter API (LLM completions)
- OpenAI Embeddings (text-embedding-3-small)
- SUPADATA API (YouTube transcription)

### How It Works

1. **Transcription**: YouTube videos are transcribed via SUPADATA API
2. **Chunking**: Transcripts split into 700-token chunks (20% overlap)
3. **Embedding**: Each chunk embedded using OpenAI's embedding model
4. **Indexing**: Embeddings stored in Qdrant vector database
5. **Retrieval**: User questions trigger semantic search (top 12 chunks)
6. **Grading**: LLM filters chunks for relevance
7. **Generation**: Context + question sent to LLM for answer

---

## Project Structure

```
.
├── backend/              # FastAPI application
│   ├── app/             # Application code
│   │   ├── api/         # REST and WebSocket endpoints
│   │   ├── services/    # Business logic
│   │   ├── models/      # Database models
│   │   └── rag/         # RAG pipeline (LangGraph)
│   ├── tests/           # Backend tests
│   └── alembic/         # Database migrations
├── frontend/            # Astro application
│   ├── src/
│   │   ├── pages/       # Route pages
│   │   ├── components/  # UI components
│   │   └── stores/      # State management
│   └── public/          # Static assets
├── docker-compose.yml   # PostgreSQL + Qdrant
└── dev.sh              # Development startup script
```

---

## Development

### Running Tests

```bash
# Backend tests
cd backend
source .venv/bin/activate
pytest tests/ --cov=app

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Backend
cd backend
black app/ tests/              # Format
ruff check app/ tests/         # Lint

# Frontend
cd frontend
npm run lint                   # Lint
npm run format                 # Format
```

### Stopping Services

```bash
./stop.sh           # Stop backend + frontend
./stop.sh --all     # Stop everything including Docker
```

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Detailed setup guide
- **[CLAUDE.md](CLAUDE.md)** - Development guide for Claude Code agents
- **[PRODUCTION_NOTES.md](PRODUCTION_NOTES.md)** - Production deployment
- **API Documentation** - http://localhost:8000/docs (when running)

---

## License

[Your License Here]

---

**Built with:**
FastAPI | Astro | PostgreSQL | Qdrant | LangChain | OpenRouter | OpenAI
