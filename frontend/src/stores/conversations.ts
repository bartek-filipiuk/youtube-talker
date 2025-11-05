/**
 * Conversations State Management
 * Manages the list of user conversations for the sidebar with pagination
 */

import { atom } from 'nanostores';
import type { Conversation } from '../lib/api';

export interface ConversationListState {
  conversations: Conversation[];
  total: number;
  currentPage: number;
  limit: number;
  loading: boolean;
  error: string | null;
}

// Conversation list state with pagination
export const $conversationList = atom<ConversationListState>({
  conversations: [],
  total: 0,
  currentPage: 0,
  limit: 10,
  loading: false,
  error: null
});

// Active conversation ID (for highlighting in sidebar)
export const $activeConversationId = atom<string | null>(null);

// Backward compatibility - exported for components still using old API
export const $conversations = atom<Conversation[]>([]);

/**
 * Set conversations list
 */
export function setConversations(conversations: Conversation[]): void {
  $conversations.set(conversations);
}

/**
 * Set active conversation ID
 */
export function setActiveConversation(id: string | null): void {
  $activeConversationId.set(id);
}

/**
 * Add a new conversation to the list
 */
export function addConversation(conversation: Conversation): void {
  const current = $conversations.get();
  $conversations.set([conversation, ...current]); // Add to beginning
}

/**
 * Remove a conversation from the list
 */
export function removeConversation(id: string): void {
  const current = $conversations.get();
  $conversations.set(current.filter(c => c.id !== id));
}

/**
 * Clear all conversations
 */
export function clearConversations(): void {
  $conversations.set([]);
  $activeConversationId.set(null);
}

// New pagination-aware actions
export function setConversationsWithPagination(conversations: Conversation[], total: number) {
  $conversationList.set({
    ...$conversationList.get(),
    conversations,
    total,
    loading: false,
    error: null
  });
}

export function setConversationsLoading(loading: boolean) {
  $conversationList.set({ ...$conversationList.get(), loading });
}

export function setConversationsError(error: string) {
  $conversationList.set({ ...$conversationList.get(), loading: false, error });
}

export function removeConversationPaginated(id: string) {
  const state = $conversationList.get();
  $conversationList.set({
    ...state,
    conversations: state.conversations.filter(c => c.id !== id),
    total: state.total - 1
  });
}

export function nextConversationPage() {
  const state = $conversationList.get();
  const maxPage = Math.ceil(state.total / state.limit) - 1;
  if (state.currentPage < maxPage) {
    $conversationList.set({ ...state, currentPage: state.currentPage + 1 });
  }
}

export function prevConversationPage() {
  const state = $conversationList.get();
  if (state.currentPage > 0) {
    $conversationList.set({ ...state, currentPage: state.currentPage - 1 });
  }
}
