/**
 * Chat State Management with Nanostores
 * Manages messages and chat UI state
 */

import { atom } from 'nanostores';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

// Chat state atoms
export const $messages = atom<Message[]>([]);
export const $isTyping = atom<boolean>(false);
export const $currentStreamingMessage = atom<string>('');

/**
 * Add a message to the chat
 */
export function addMessage(role: 'user' | 'assistant', content: string): void {
  const message: Message = {
    id: crypto.randomUUID(),
    role,
    content,
    timestamp: new Date(),
  };

  $messages.set([...$messages.get(), message]);
}

/**
 * Start streaming an assistant message
 */
export function startStreaming(): void {
  $isTyping.set(true);
  $currentStreamingMessage.set('');

  // Add placeholder message for streaming
  const streamingMessage: Message = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    isStreaming: true,
  };

  $messages.set([...$messages.get(), streamingMessage]);
}

/**
 * Append content to the currently streaming message
 */
export function appendToStream(chunk: string): void {
  const messages = $messages.get();
  const lastMessage = messages[messages.length - 1];

  if (lastMessage && lastMessage.isStreaming) {
    // Update the last message with accumulated content
    const updatedMessage = {
      ...lastMessage,
      content: lastMessage.content + chunk,
    };

    $messages.set([...messages.slice(0, -1), updatedMessage]);
  }
}

/**
 * Finalize streaming (message complete)
 */
export function finalizeStreaming(): void {
  $isTyping.set(false);

  const messages = $messages.get();
  const lastMessage = messages[messages.length - 1];

  if (lastMessage && lastMessage.isStreaming) {
    // Remove streaming flag
    const finalizedMessage = {
      ...lastMessage,
      isStreaming: false,
    };

    $messages.set([...messages.slice(0, -1), finalizedMessage]);
  }
}

/**
 * Clear all messages
 */
export function clearMessages(): void {
  $messages.set([]);
  $isTyping.set(false);
  $currentStreamingMessage.set('');
}

/**
 * Set typing indicator
 */
export function setTyping(isTyping: boolean): void {
  $isTyping.set(isTyping);
}
