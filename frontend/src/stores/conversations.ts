/**
 * Conversations State Management
 * Manages the list of user conversations for the sidebar
 */

import { atom } from 'nanostores';
import type { Conversation } from '../lib/api';

// Conversation list state
export const $conversations = atom<Conversation[]>([]);

// Active conversation ID (for highlighting in sidebar)
export const $activeConversationId = atom<string | null>(null);

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
