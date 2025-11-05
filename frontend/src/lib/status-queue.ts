/**
 * Status Message Queue
 *
 * Manages a queue of status messages (e.g., "Searching...", "AI is typing...")
 * that display vertically without overlapping.
 *
 * Usage:
 * ```typescript
 * const queue = new StatusQueue('statusContainer');
 * queue.add('searching', 'Searching in knowledge base...');
 * queue.add('typing', 'AI is typing...');
 * queue.remove('searching');
 * ```
 */

export interface StatusMessage {
  id: string;
  text: string;
  element: HTMLDivElement;
}

export class StatusQueue {
  private container: HTMLElement;
  private messages: Map<string, StatusMessage> = new Map();

  constructor(containerId: string) {
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Status queue container '${containerId}' not found`);
    }
    this.container = container;
  }

  /**
   * Add or update a status message
   * @param id - Unique identifier for this message (e.g., 'typing', 'searching')
   * @param text - Message text to display
   */
  add(id: string, text: string): void {
    // If message already exists, update its text
    if (this.messages.has(id)) {
      const existing = this.messages.get(id)!;
      const textSpan = existing.element.querySelector('span.text-sm');
      if (textSpan) {
        textSpan.textContent = text;
      }
      return;
    }

    // Create new message element
    const messageEl = document.createElement('div');
    messageEl.className = 'flex items-center gap-2 text-gray-500 py-1 animate-fade-in';
    messageEl.dataset.statusId = id;

    // Add animated dots
    const dotsContainer = document.createElement('div');
    dotsContainer.className = 'flex gap-1';

    for (let i = 0; i < 3; i++) {
      const dot = document.createElement('span');
      dot.className = 'w-2 h-2 bg-gray-400 rounded-full animate-bounce';
      dot.style.animationDelay = `${i * 150}ms`;
      dotsContainer.appendChild(dot);
    }

    // Add text
    const textSpan = document.createElement('span');
    textSpan.className = 'text-sm';
    textSpan.textContent = text;

    messageEl.appendChild(dotsContainer);
    messageEl.appendChild(textSpan);

    // Add to container
    this.container.appendChild(messageEl);
    this.container.classList.remove('hidden');

    // Store in map
    this.messages.set(id, {
      id,
      text,
      element: messageEl,
    });
  }

  /**
   * Remove a status message
   * @param id - Identifier of the message to remove
   */
  remove(id: string): void {
    const message = this.messages.get(id);
    if (!message) return;

    // Fade out animation
    message.element.classList.add('animate-fade-out');

    setTimeout(() => {
      message.element.remove();
      this.messages.delete(id);

      // Hide container if no messages left
      if (this.messages.size === 0) {
        this.container.classList.add('hidden');
      }
    }, 200);
  }

  /**
   * Remove all status messages
   */
  clear(): void {
    for (const id of this.messages.keys()) {
      this.remove(id);
    }
  }

  /**
   * Check if a message exists
   */
  has(id: string): boolean {
    return this.messages.has(id);
  }

  /**
   * Get the number of active messages
   */
  get size(): number {
    return this.messages.size;
  }
}
