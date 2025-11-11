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

export interface User {
  id: string;
  email: string;
  role: string;
  transcript_count: number;
  created_at: string;
}

export interface UsersListResponse {
  users: User[];
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

// ============================================================================
// Users
// ============================================================================

export interface CreateUserRequest {
  email: string;
}

export interface CreateUserResponse {
  user: User;
  generated_password: string;
}

/**
 * Create new user with auto-generated password (admin only)
 */
export async function createUser(token: string, email: string): Promise<CreateUserResponse> {
  return adminFetch<CreateUserResponse>('/admin/users', token, {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

/**
 * List all users (admin only)
 */
export async function listUsers(token: string, limit: number = 50, offset: number = 0): Promise<UsersListResponse> {
  return adminFetch<UsersListResponse>(`/admin/users?limit=${limit}&offset=${offset}`, token);
}

/**
 * Reset user password with auto-generated password (admin only)
 */
export async function resetUserPassword(token: string, userId: string): Promise<CreateUserResponse> {
  return adminFetch<CreateUserResponse>(`/admin/users/${userId}/reset-password`, token, {
    method: 'POST',
  });
}

/**
 * Delete user and all related data (admin only)
 */
export async function deleteUser(token: string, userId: string): Promise<void> {
  await adminFetch<void>(`/admin/users/${userId}`, token, {
    method: 'DELETE',
  });
}

// ============================================================================
// Settings
// ============================================================================

export interface RegistrationStatus {
  enabled: boolean;
}

/**
 * Get registration status (admin only)
 */
export async function getRegistrationStatus(token: string): Promise<RegistrationStatus> {
  return adminFetch<RegistrationStatus>('/admin/settings/registration', token);
}

/**
 * Set registration status (admin only)
 */
export async function setRegistrationStatus(token: string, enabled: boolean): Promise<RegistrationStatus> {
  return adminFetch<RegistrationStatus>('/admin/settings/registration', token, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  });
}
