/**
 * Markdown Rendering Utility
 *
 * Safely converts markdown to HTML with XSS protection via isomorphic-dompurify.
 * Used for displaying formatted AI responses in the chat interface.
 *
 * Uses isomorphic-dompurify for compatibility with both browser and Node.js (SSR) environments.
 */

import { marked } from 'marked';
import DOMPurify from 'isomorphic-dompurify';

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

  let rawHtml: string;

  try {
    // In marked v16+, we need to be explicit about synchronous parsing
    // Use marked() directly with async: false option
    const result = marked(content, { async: false, breaks: true, gfm: true });

    // If result is a Promise (shouldn't be with async: false), handle it
    if (result instanceof Promise) {
      console.error('Unexpected Promise returned from marked()');
      rawHtml = content; // Fallback to raw content
    } else {
      rawHtml = result as string;
    }
  } catch (error) {
    console.error('Markdown parsing error:', error);
    rawHtml = content; // Fallback to raw content
  }

  // Sanitize to prevent XSS attacks
  const cleanHtml = DOMPurify.sanitize(rawHtml);

  return cleanHtml;
}
