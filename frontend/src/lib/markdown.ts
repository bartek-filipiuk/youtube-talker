/**
 * Markdown Rendering Utility
 *
 * Safely converts markdown to HTML with XSS protection via DOMPurify.
 * Used for displaying formatted AI responses in the chat interface.
 */

import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * Convert markdown string to sanitized HTML
 *
 * @param content - Raw markdown text
 * @returns Sanitized HTML string safe for rendering
 *
 * @example
 * const html = renderMarkdown("**Bold** text with `code`");
 * // Returns: "<p><strong>Bold</strong> text with <code>code</code></p>"
 */
export function renderMarkdown(content: string): string {
  if (!content) {
    return '';
  }

  // Convert markdown to HTML
  const rawHtml = marked.parse(content);

  // Sanitize to prevent XSS attacks
  const cleanHtml = DOMPurify.sanitize(rawHtml);

  return cleanHtml;
}
