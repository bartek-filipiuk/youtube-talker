/**
 * Admin Authentication Utilities for SSR
 *
 * Provides server-side admin authentication checks for Astro pages.
 * Use requireAdmin() in Astro frontmatter to protect admin routes.
 */

import type { AstroGlobal } from 'astro';
import { API_BASE } from './api';

export interface AdminUser {
  id: string;
  email: string;
  role: string;
}

export interface AdminAuthResult {
  token: string;
  user: AdminUser;
}

/**
 * Require admin authentication in SSR context.
 *
 * Checks for valid token in cookies/localStorage and verifies admin status.
 * Redirects to home page if not authenticated or not admin.
 *
 * Usage in Astro frontmatter:
 * ```astro
 * ---
 * import { requireAdmin } from '@/lib/admin-auth';
 * const auth = await requireAdmin(Astro);
 * if (auth instanceof Response) return auth;
 * // auth.user.email, auth.token available here
 * ---
 * ```
 *
 * @param Astro - Astro global object
 * @returns AdminAuthResult if authenticated admin, or Response (redirect) if not
 */
export async function requireAdmin(Astro: AstroGlobal): Promise<AdminAuthResult | Response> {
  // Step 1: Get token from cookies first, fallback to query param (for client-side transitions)
  let token = Astro.cookies.get('token')?.value;

  // Fallback: Check URL query params (e.g., /admin?token=xxx from client-side navigation)
  if (!token) {
    token = Astro.url.searchParams.get('token') || undefined;
  }

  // No token found - redirect to login
  if (!token) {
    return Astro.redirect('/?error=auth_required');
  }

  // Step 2: Validate token with backend
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    // Token invalid or expired
    if (!response.ok) {
      if (response.status === 401) {
        return Astro.redirect('/?error=session_expired');
      }
      throw new Error(`Auth check failed: ${response.status}`);
    }

    const user: AdminUser = await response.json();

    // Step 3: Verify admin status
    if (user.role !== 'admin') {
      return Astro.redirect('/?error=admin_required');
    }

    // Step 4: Return auth result for use in page
    return {
      token,
      user,
    };

  } catch (error) {
    console.error('Admin auth check failed:', error);
    return Astro.redirect('/?error=auth_error');
  }
}

/**
 * Optional: Set token in cookie for SSR auth
 * Call this from a client-side script when user logs in
 *
 * Usage:
 * ```typescript
 * // After successful login
 * document.cookie = `token=${token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=Strict`;
 * ```
 */
export function setAuthCookie(token: string, maxAgeDays: number = 7): void {
  const maxAgeSeconds = maxAgeDays * 24 * 60 * 60;
  document.cookie = `token=${token}; path=/; max-age=${maxAgeSeconds}; SameSite=Strict`;
}

/**
 * Optional: Clear auth cookie on logout
 */
export function clearAuthCookie(): void {
  document.cookie = 'token=; path=/; max-age=0';
}
