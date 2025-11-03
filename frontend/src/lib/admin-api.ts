/**
 * Admin API Client Utilities
 *
 * Provides typed API client functions for admin operations.
 * All functions require admin authentication token.
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
  qdrant_collection_name: string;
  created_by: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  video_count?: number;
}

export interface ChannelVideo {
  id: string;
  youtube_video_id: string;
  title: string;
  channel_id: string;
  processing_status: string;
  added_at: string;
  total_chunks?: number;
}

export interface AdminStats {
  total_channels: number;
  active_channels: number;
  total_videos: number;
}

export interface CreateChannelRequest {
  name: string;
  display_title: string;
  description?: string;
}

export interface UpdateChannelRequest {
  display_title?: string;
  description?: string;
}

export interface AddVideoRequest {
  youtube_url: string;
}

// ============================================================================
// API Client
// ============================================================================

/**
 * Base fetch wrapper with auth and error handling
 */
async function adminFetch<T>(
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

  return response.json();
}

// ============================================================================
// Stats
// ============================================================================

/**
 * Fetch admin dashboard stats
 */
export async function getAdminStats(token: string): Promise<AdminStats> {
  return adminFetch<AdminStats>('/admin/stats', token);
}

// ============================================================================
// Channels
// ============================================================================

/**
 * List all channels (active and inactive)
 */
export async function listChannels(token: string): Promise<Channel[]> {
  const response = await adminFetch<{ channels: Channel[]; total: number; limit: number; offset: number }>(
    '/admin/channels',
    token
  );
  return response.channels;
}

/**
 * Get single channel by ID
 */
export async function getChannel(token: string, channelId: string): Promise<Channel> {
  return adminFetch<Channel>(`/admin/channels/${channelId}`, token);
}

/**
 * Create new channel
 */
export async function createChannel(
  token: string,
  data: CreateChannelRequest
): Promise<Channel> {
  return adminFetch<Channel>('/admin/channels', token, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update existing channel
 */
export async function updateChannel(
  token: string,
  channelId: string,
  data: UpdateChannelRequest
): Promise<Channel> {
  return adminFetch<Channel>(`/admin/channels/${channelId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Soft delete channel (set is_active=false)
 */
export async function deleteChannel(token: string, channelId: string): Promise<void> {
  await adminFetch<void>(`/admin/channels/${channelId}`, token, {
    method: 'DELETE',
  });
}

// ============================================================================
// Channel Videos
// ============================================================================

/**
 * List all videos in a channel
 */
export async function listChannelVideos(
  token: string,
  channelId: string
): Promise<ChannelVideo[]> {
  const response = await adminFetch<{ videos: ChannelVideo[]; total: number; limit: number; offset: number }>(
    `/admin/channels/${channelId}/videos`,
    token
  );
  return response.videos;
}

/**
 * Add video to channel
 */
export async function addVideoToChannel(
  token: string,
  channelId: string,
  data: AddVideoRequest
): Promise<ChannelVideo> {
  return adminFetch<ChannelVideo>(`/admin/channels/${channelId}/videos`, token, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Remove video from channel
 */
export async function removeVideoFromChannel(
  token: string,
  channelId: string,
  videoId: string
): Promise<void> {
  await adminFetch<void>(`/admin/channels/${channelId}/videos/${videoId}`, token, {
    method: 'DELETE',
  });
}
