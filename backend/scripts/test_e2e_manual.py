#!/usr/bin/env python3
"""
Manual E2E Test Script for Backend

Tests the complete RAG pipeline end-to-end:
1. Health checks
2. User authentication
3. YouTube transcript ingestion
4. WebSocket chat with RAG
5. Data persistence verification

Usage:
    python scripts/test_e2e_manual.py
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

import httpx
import websockets


# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

# Test data
TEST_EMAIL = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
TEST_PASSWORD = "testpass123"

# Use a short, public educational video for testing
# This is a 1-minute video about Python basics
TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=kqtD5dpn9C8"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_step(step: int, title: str):
    """Print formatted step header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}Step {step}: {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")


async def test_health_checks() -> bool:
    """Test all health check endpoints."""
    print_step(1, "Health Checks")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Basic health
            response = await client.get(f"{BASE_URL}/api/health")
            if response.status_code == 200:
                print_success(f"Basic health: {response.json()}")
            else:
                print_error(f"Basic health failed: {response.status_code}")
                return False

            # Database health
            response = await client.get(f"{BASE_URL}/api/health/db")
            if response.status_code == 200:
                print_success(f"Database health: {response.json()}")
            else:
                print_error(f"Database health failed: {response.status_code}")
                return False

            # Qdrant health
            response = await client.get(f"{BASE_URL}/api/health/qdrant")
            if response.status_code == 200:
                print_success(f"Qdrant health: {response.json()}")
            else:
                print_error(f"Qdrant health failed: {response.status_code}")
                return False

            return True

        except Exception as e:
            print_error(f"Health check failed: {e}")
            return False


async def test_authentication() -> Optional[str]:
    """Test user registration and login, return token."""
    print_step(2, "Authentication")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Register user
            print_info(f"Registering user: {TEST_EMAIL}")
            response = await client.post(
                f"{BASE_URL}/api/auth/register",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
            )
            if response.status_code == 201:
                user_data = response.json()
                print_success(f"User registered: {user_data['id']}")
            else:
                print_error(f"Registration failed: {response.status_code} - {response.text}")
                return None

            # Login
            print_info("Logging in...")
            response = await client.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
            )
            if response.status_code == 200:
                login_data = response.json()
                token = login_data["token"]
                print_success(f"Login successful, token: {token[:20]}...")
                return token
            else:
                print_error(f"Login failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print_error(f"Authentication failed: {e}")
            return None


async def test_transcript_ingestion(token: str) -> bool:
    """Test YouTube transcript ingestion."""
    print_step(3, "YouTube Transcript Ingestion")

    async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout for ingestion
        try:
            print_info(f"Ingesting video: {TEST_YOUTUBE_URL}")
            print_info("This may take 10-30 seconds (fetching transcript, chunking, embedding)...")

            response = await client.post(
                f"{BASE_URL}/api/transcripts/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json={"youtube_url": TEST_YOUTUBE_URL}
            )

            if response.status_code == 201:
                result = response.json()
                print_success("Transcript ingested successfully!")
                print_info(f"Video ID: {result['youtube_video_id']}")
                print_info(f"Chunks created: {result['chunk_count']}")
                print_info(f"Metadata: {result.get('metadata', {})}")
                return True
            elif response.status_code == 409:
                print_info("Transcript already exists (expected if running test multiple times)")
                return True
            else:
                print_error(f"Ingestion failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print_error(f"Ingestion failed: {e}")
            return False


async def test_websocket_chat(token: str) -> Optional[str]:
    """Test WebSocket chat with RAG pipeline."""
    print_step(4, "WebSocket Chat with RAG")

    conversation_id = None

    try:
        uri = f"{WS_URL}/api/ws/chat?token={token}"
        print_info(f"Connecting to WebSocket: {uri}")

        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as websocket:
            # Receive welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print_success(f"Connected: {welcome_data.get('message')}")

            # Send Q&A query about the video
            query = "What is the main topic of this video?"
            print_info(f"Sending query: {query}")

            await websocket.send(json.dumps({
                "type": "message",
                "content": query,
                "conversation_id": "new"
            }))

            # Receive responses (status updates and final response)
            response_count = 0
            assistant_response = None

            while response_count < 10:  # Max 10 messages to avoid infinite loop
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "status":
                        print_info(f"Status: {data.get('message')} (step: {data.get('step')})")

                    elif msg_type == "assistant":
                        assistant_response = data.get("content")
                        metadata = data.get("metadata", {})
                        conversation_id = metadata.get("conversation_id")

                        print_success("Response received!")
                        print_info(f"Intent: {metadata.get('intent')}")
                        print_info(f"Conversation ID: {conversation_id}")
                        print_info(f"Response (first 200 chars): {assistant_response[:200]}...")

                        # If chunks were used, show count
                        if metadata.get("chunks_used"):
                            print_info(f"Chunks used: {metadata.get('chunks_used')}")

                        break

                    elif msg_type == "error":
                        print_error(f"Error: {data.get('message')} (code: {data.get('code')})")
                        break

                    response_count += 1

                except asyncio.TimeoutError:
                    print_error("Timeout waiting for response")
                    break

            if assistant_response:
                return conversation_id
            else:
                print_error("No assistant response received")
                return None

    except Exception as e:
        print_error(f"WebSocket chat failed: {e}")
        return None


async def test_data_persistence(token: str, conversation_id: Optional[str]) -> bool:
    """Test that conversation and messages were saved."""
    print_step(5, "Data Persistence Verification")

    if not conversation_id:
        print_error("No conversation ID to verify")
        return False

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # List conversations
            print_info("Fetching conversations list...")
            response = await client.get(
                f"{BASE_URL}/api/conversations",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                data = response.json()
                print_success(f"Found {data['total']} conversation(s)")
            else:
                print_error(f"Failed to list conversations: {response.status_code}")
                return False

            # Get conversation detail
            print_info(f"Fetching conversation {conversation_id}...")
            response = await client.get(
                f"{BASE_URL}/api/conversations/{conversation_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                print_success(f"Conversation found with {len(messages)} message(s)")

                # Verify we have both user and assistant messages
                user_messages = [m for m in messages if m["role"] == "user"]
                assistant_messages = [m for m in messages if m["role"] == "assistant"]

                print_info(f"User messages: {len(user_messages)}")
                print_info(f"Assistant messages: {len(assistant_messages)}")

                if user_messages and assistant_messages:
                    print_success("Both user and assistant messages saved correctly!")
                    return True
                else:
                    print_error("Missing messages")
                    return False
            else:
                print_error(f"Failed to get conversation: {response.status_code}")
                return False

        except Exception as e:
            print_error(f"Data persistence check failed: {e}")
            return False


async def main():
    """Run all E2E tests."""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}Backend E2E Test Suite{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")

    start_time = datetime.now()

    # Step 1: Health checks
    if not await test_health_checks():
        print_error("\n❌ Health checks failed. Is the backend server running?")
        sys.exit(1)

    # Step 2: Authentication
    token = await test_authentication()
    if not token:
        print_error("\n❌ Authentication failed")
        sys.exit(1)

    # Step 3: Transcript ingestion
    if not await test_transcript_ingestion(token):
        print_error("\n❌ Transcript ingestion failed")
        sys.exit(1)

    # Step 4: WebSocket chat
    conversation_id = await test_websocket_chat(token)
    if not conversation_id:
        print_error("\n❌ WebSocket chat failed")
        sys.exit(1)

    # Step 5: Data persistence
    if not await test_data_persistence(token, conversation_id):
        print_error("\n❌ Data persistence verification failed")
        sys.exit(1)

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}✅ ALL TESTS PASSED!{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    print(f"{Colors.GREEN}Total time: {duration:.1f} seconds{Colors.END}")
    print(f"{Colors.GREEN}Backend is ready for frontend integration! 🚀{Colors.END}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)
