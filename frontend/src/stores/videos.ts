/**
 * Video List Store
 *
 * State management for video list with pagination
 */

import { atom } from 'nanostores';

export interface Video {
  id: string;
  title: string;
  created_at: string;
}

export interface VideoListState {
  videos: Video[];
  total: number;
  currentPage: number;
  limit: number;
  loading: boolean;
  error: string | null;
}

export const $videoList = atom<VideoListState>({
  videos: [],
  total: 0,
  currentPage: 0,
  limit: 10,
  loading: false,
  error: null
});

// Actions
export function setVideos(videos: Video[], total: number) {
  $videoList.set({
    ...$videoList.get(),
    videos,
    total,
    loading: false,
    error: null
  });
}

export function setLoading(loading: boolean) {
  $videoList.set({ ...$videoList.get(), loading });
}

export function setError(error: string) {
  $videoList.set({ ...$videoList.get(), loading: false, error });
}

export function removeVideo(videoId: string) {
  const state = $videoList.get();
  $videoList.set({
    ...state,
    videos: state.videos.filter(v => v.id !== videoId),
    total: state.total - 1
  });
}

export function nextPage() {
  const state = $videoList.get();
  const maxPage = Math.ceil(state.total / state.limit) - 1;
  if (state.currentPage < maxPage) {
    $videoList.set({ ...state, currentPage: state.currentPage + 1 });
  }
}

export function prevPage() {
  const state = $videoList.get();
  if (state.currentPage > 0) {
    $videoList.set({ ...state, currentPage: state.currentPage - 1 });
  }
}
