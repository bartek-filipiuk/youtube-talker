# Qivio Monetization Plan

**Goal:** Add Stripe subscriptions with usage limits and EU legal compliance.

**Tiers:**
| Tier | Videos | Messages | Price |
|------|--------|----------|-------|
| Free | 3/mo | 50/mo | $0 |
| Pro | 50/mo | 1,000/mo | $12/mo or $115/yr |
| Enterprise | Custom | Custom | Contact sales |

---

## Phase 1: Security Hardening ✅

Before accepting payments, fix security gaps.

### Tasks

- [x] **1.1** Restrict CORS in `backend/app/core/middleware.py`
  - Changed `allow_methods=["*"]` to `["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]`
  - Changed `allow_headers=["*"]` to specific headers

- [x] **1.2** Add security headers middleware
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: (restrictive)`

- [x] **1.3** Validate SECRET_KEY on startup in `backend/app/config.py`
  - Fails if using default value in production

- [x] **1.4** Add session invalidation on password change
  - Modified `backend/app/api/routes/auth.py`

---

## Phase 2: Database Schema ✅

Add tables for subscriptions and usage tracking.

### Tasks

- [x] **2.1** Create `subscription_plans` table
  - Created in `backend/app/db/models.py`

- [x] **2.2** Create `user_subscriptions` table
  - Created in `backend/app/db/models.py`

- [x] **2.3** Create `usage_tracking` table
  - Created in `backend/app/db/models.py`

- [x] **2.4** Create migration files in `backend/alembic/versions/`
  - `526b978706b1_add_subscription_and_usage_tracking_.py`

- [x] **2.5** Seed Free and Pro plans
  - Created `backend/scripts/seed_plans.py`

---

## Phase 3: Stripe Backend ✅

Integrate Stripe for checkout and subscription management.

### Setup (Manual)

- [x] **3.1** Create Stripe account (sandbox mode)
- [x] **3.2** Create Products in Stripe Dashboard:
  - "Qivio Pro Monthly" - $12/month
  - "Qivio Pro Annual" - $115/year
- [ ] **3.3** Configure Customer Portal in Stripe (pending)
- [ ] **3.4** Add webhook endpoint URL (pending - needs deployment)

### Implementation

- [x] **3.5** Add Stripe config to `.env` and `backend/app/config.py`
  - Config settings added with validation

- [x] **3.6** Create `backend/app/services/stripe_service.py`
  - `create_checkout_session()`
  - `create_portal_session()`
  - `get_subscription()`
  - `cancel_subscription()`

- [x] **3.7** Create `backend/app/api/routes/billing.py`
  - `GET /api/billing/plans` - List available plans
  - `GET /api/billing/status` - Current subscription status
  - `POST /api/billing/checkout` - Create checkout session
  - `POST /api/billing/portal` - Create customer portal session
  - `GET /api/billing/usage` - Current usage stats

- [x] **3.8** Create `backend/app/api/routes/stripe_webhook.py`
  - Handles: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`

---

## Phase 4: Usage Enforcement ✅

Check limits before expensive operations.

### Tasks

- [x] **4.1** Create `backend/app/services/usage_service.py`
  - `enforce_video_limit(user_id)` - raises UsageLimitExceededError if exceeded
  - `enforce_message_limit(user_id)` - raises UsageLimitExceededError if exceeded
  - `record_video_usage(user_id)` - increment after successful operation
  - `record_message_usage(user_id)` - increment after successful operation

- [x] **4.2** Add usage check before video ingestion
  - Modified `backend/app/api/routes/transcripts.py`
  - Checks limit before ingestion, records usage after success

- [x] **4.3** Add usage check before chat message
  - Modified `backend/app/api/websocket/chat_handler.py`
  - Checks limit before processing, records usage after success

- [x] **4.4** Add `UsageLimitExceededError` exception
  - Added to `backend/app/core/errors.py`
  - Added handler in `backend/app/core/exception_handlers.py` (returns 402)
  - Registered in `backend/app/main.py`

---

## Phase 5: Frontend Billing ✅

Add pricing and billing pages.

### Tasks

- [x] **5.1** Create `/pricing` page
  - Public page with Free vs Pro comparison
  - Billing cycle toggle (Monthly/Annual)
  - Checkout button with Stripe integration

- [x] **5.2** Create `/billing` page (protected)
  - Current plan status with badge
  - Usage stats with progress bars
  - Manage subscription button (opens Stripe Portal)
  - Cancel warning display

- [x] **5.3** Add usage indicator in app header
  - Dropdown with usage bars
  - Plan name display
  - Link to billing page

- [x] **5.4** Add limit reached modal
  - LimitReachedModal component
  - Triggered via custom event
  - Shows Pro benefits and upgrade CTA

---

## Phase 6: Legal Compliance (EU/GDPR) ✅

Required documents for EU company with payments.

### Tasks

- [x] **6.1** Create `/privacy` page
  - Created `frontend/src/pages/privacy.astro`
  - Lists Stripe, OpenRouter, OpenAI, SUPADATA as processors
  - GDPR rights section included
  - Template note for legal review

- [x] **6.2** Create `/terms` page
  - Created `frontend/src/pages/terms.astro`
  - Service terms, payment terms, refund policy
  - Governing law: Poland
  - EU consumer rights and ODR link

- [x] **6.3** Add cookie consent banner
  - Created `frontend/src/components/CookieConsent.astro`
  - Essential cookies only (session)
  - Saves preference in localStorage

- [x] **6.4** Add footer with links
  - Created `frontend/src/components/Footer.astro`
  - Links to Privacy Policy, Terms of Service, Pricing
  - Added to Layout with showFooter prop

---

## Files Summary

### New Backend Files
```
app/services/stripe_service.py
app/services/usage_service.py
app/services/billing_service.py
app/api/routes/billing.py
app/api/routes/stripe_webhook.py
app/db/repositories/subscription_repo.py
app/db/repositories/usage_repo.py
app/schemas/billing.py
alembic/versions/xxx_add_subscription_tables.py
scripts/seed_plans.py
```

### Modified Backend Files
```
app/config.py                         # Stripe config
app/core/middleware.py                # Security headers
app/dependencies.py                   # Subscription deps
app/services/auth_service.py          # Session invalidation
app/services/transcript_service.py    # Usage check
app/api/websocket/chat_handler.py     # Usage check
app/db/models.py                      # New models
```

### New Frontend Files
```
src/pages/pricing.astro        # Public pricing page with checkout
src/pages/billing.astro        # Protected subscription management
src/pages/privacy.astro        # GDPR-compliant privacy policy
src/pages/terms.astro          # Terms of service
src/components/LimitReachedModal.astro  # Usage limit modal
src/components/CookieConsent.astro      # Cookie consent banner
src/components/Footer.astro    # Footer with legal links
src/lib/api.ts                 # Added billing API functions
```

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Security | ✅ COMPLETED | CORS restricted, security headers added, SECRET_KEY validation, session invalidation |
| 2. Database | ✅ COMPLETED | subscription_plans, user_subscriptions, usage_tracking tables created and seeded |
| 3. Stripe Backend | ✅ COMPLETED | stripe_service.py, billing.py routes, stripe_webhook.py, billing_service.py |
| 4. Usage Enforcement | ✅ COMPLETED | usage_service.py, video/message limit checks, UsageLimitExceededError |
| 5. Frontend Billing | ✅ COMPLETED | pricing.astro, billing.astro, Header usage dropdown, LimitReachedModal |
| 6. Legal | ✅ COMPLETED | privacy.astro, terms.astro, CookieConsent, Footer component |

---

## Notes

- Start with test mode in Stripe
- Legal docs need professional review before launch
- Enterprise tier is manual (contact sales) - no automation needed
- Cookie consent can use free tier of cookie-script.com
