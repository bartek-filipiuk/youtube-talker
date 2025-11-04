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

// Configure marked with custom renderer for better styling
const renderer = new marked.Renderer();

// Custom code block rendering with language label and copy button support
renderer.code = ({ text, lang }: { text: string; lang?: string }) => {
  const language = lang || 'text';
  const escapedCode = escapeHtml(text);

  return `
    <div class="code-block-container my-4 rounded-lg overflow-hidden border border-gray-200 shadow-sm">
      <div class="code-header flex items-center justify-between bg-gray-800 text-gray-300 px-4 py-2 text-sm">
        <span class="font-mono">${language}</span>
        <button class="copy-code-btn text-gray-400 hover:text-white transition px-2 py-1 rounded hover:bg-gray-700" data-code="${escapedCode.replace(/"/g, '&quot;')}">
          Copy
        </button>
      </div>
      <pre class="bg-gray-900 text-gray-100 p-4 overflow-x-auto"><code class="language-${language}">${escapedCode}</code></pre>
    </div>
  `;
};

// Inline code with better styling
renderer.codespan = ({ text }: { text: string }) => {
  return `<code class="inline-code bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono">${escapeHtml(text)}</code>`;
};

// Headings with better styling
renderer.heading = ({ text, depth }: { text: string; depth: number }) => {
  const sizes: Record<number, string> = {
    1: 'text-2xl',
    2: 'text-xl',
    3: 'text-lg',
    4: 'text-base',
    5: 'text-sm',
    6: 'text-xs'
  };
  return `<h${depth} class="${sizes[depth] || 'text-base'} font-bold text-gray-900 mt-6 mb-3">${text}</h${depth}>`;
};

// Paragraphs with spacing
renderer.paragraph = ({ text }: { text: string }) => {
  return `<p class="mb-4 text-gray-800 leading-relaxed">${text}</p>`;
};

// Lists with better styling
renderer.list = ({ items, ordered }: { items: string; ordered: boolean }) => {
  const tag = ordered ? 'ol' : 'ul';
  const classes = ordered
    ? 'list-decimal list-inside space-y-2 mb-4 pl-4'
    : 'list-disc list-inside space-y-2 mb-4 pl-4';
  return `<${tag} class="${classes}">${items}</${tag}>`;
};

renderer.listitem = ({ text }: { text: string }) => {
  return `<li class="text-gray-800">${text}</li>`;
};

// Blockquotes
renderer.blockquote = ({ text }: { text: string }) => {
  return `<blockquote class="border-l-4 border-blue-500 pl-4 py-2 my-4 italic text-gray-700 bg-blue-50">${text}</blockquote>`;
};

// Links with proper styling
renderer.link = ({ href, title, text }: { href: string; title?: string; text: string }) => {
  const titleAttr = title ? `title="${escapeHtml(title)}"` : '';
  return `<a href="${escapeHtml(href)}" ${titleAttr} class="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">${text}</a>`;
};

// Helper function to escape HTML
function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, (m) => map[m] || m);
}

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

  // Defensive: ensure content is a string
  if (typeof content !== 'string') {
    console.error('⚠️ renderMarkdown received non-string:', content);
    content = String(content);
  }

  let rawHtml: string;

  try {
    // In marked v16+, we need to be explicit about synchronous parsing
    // Use marked() directly with async: false option and custom renderer
    const result = marked(content, {
      async: false,
      breaks: true,
      gfm: true,
      renderer: renderer
    });

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

  // Sanitize to prevent XSS attacks (allow our custom classes and attributes)
  const cleanHtml = DOMPurify.sanitize(rawHtml, {
    ADD_ATTR: ['data-code'],
    ADD_TAGS: ['button']
  });

  return cleanHtml;
}
