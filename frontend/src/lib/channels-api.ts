/**
 * Channels API Client
 *
 * Provides typed API client functions for channel discovery and conversations.
 * All functions require user authentication token.
 */

import { API_BASE } from './api';

// ============================================================================
// Types
// ============================================================================

export interface Channel {
  id: string;
  name: string;
  display_title: string;
  description: string | null;
  video_count: number;
  created_at: string;
}

export interface ChannelListResponse {
  channels: Channel[];
  total: number;
  limit: number;
  offset: number;
}

export interface VideoInChannel {
  transcript_id: string;
  youtube_video_id: string;
  title: string;
  channel_name: string | null;
  duration: number | null;
  added_at: string;
}

export interface ChannelVideoListResponse {
  videos: VideoInChannel[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChannelConversation {
  id: string;
  channel_id: string;
  user_id: string;
  channel_name: string;
  channel_display_title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface ChannelConversationDetail {
  conversation: ChannelConversation;
  messages: Message[];
}

export interface ChannelConversationListResponse {
  conversations: ChannelConversation[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// API Client
// ============================================================================

/**
 * Base fetch wrapper with auth and error handling
 */
async function channelFetch<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error (${response.status}): ${error}`);
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}

// ============================================================================
// Channel Discovery
// ============================================================================

/**
 * List all active channels for discovery
 */
export async function listChannels(
  token: string,
  limit: number = 50,
  offset: number = 0
): Promise<ChannelListResponse> {
  return channelFetch<ChannelListResponse>(
    `/channels?limit=${limit}&offset=${offset}`,
    token
  );
}

/**
 * Get channel details by ID
 */
export async function getChannelById(
  token: string,
  channelId: string
): Promise<Channel> {
  return channelFetch<Channel>(`/channels/${channelId}`, token);
}

/**
 * Get channel details by URL-safe name
 */
export async function getChannelByName(
  token: string,
  name: string
): Promise<Channel> {
  return channelFetch<Channel>(`/channels/by-name/${name}`, token);
}

/**
 * List videos in a channel
 */
export async function getChannelVideos(
  token: string,
  channelId: string,
  limit: number = 50,
  offset: number = 0
): Promise<ChannelVideoListResponse> {
  return channelFetch<ChannelVideoListResponse>(
    `/channels/${channelId}/videos?limit=${limit}&offset=${offset}`,
    token
  );
}

// ============================================================================
// Channel Conversations
// ============================================================================

/**
 * Get or create user's conversation with a channel
 */
export async function getOrCreateConversation(
  token: string,
  channelId: string
): Promise<ChannelConversation> {
  return channelFetch<ChannelConversation>(
    `/channels/${channelId}/conversations`,
    token,
    {
      method: 'POST',
    }
  );
}

/**
 * List user's channel conversations
 */
export async function listUserChannelConversations(
  token: string,
  limit: number = 50,
  offset: number = 0
): Promise<ChannelConversationListResponse> {
  return channelFetch<ChannelConversationListResponse>(
    `/channels/conversations?limit=${limit}&offset=${offset}`,
    token
  );
}

/**
 * Get conversation details with all messages
 */
export async function getConversationWithMessages(
  token: string,
  conversationId: string
): Promise<ChannelConversationDetail> {
  return channelFetch<ChannelConversationDetail>(
    `/channels/conversations/${conversationId}`,
    token
  );
}

/**
 * Delete user's channel conversation
 */
export async function deleteChannelConversation(
  token: string,
  conversationId: string
): Promise<void> {
  return channelFetch<void>(
    `/channels/conversations/${conversationId}`,
    token,
    {
      method: 'DELETE',
    }
  );
}
