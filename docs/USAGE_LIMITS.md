# Usage Limits and Reset Mechanism

This document explains how Qivio tracks and enforces usage limits for different subscription plans.

---

## Plan Limits

| Plan       | Videos/Month | Messages/Month | Price        |
|------------|--------------|----------------|--------------|
| Free       | 3            | 50             | $0           |
| Pro        | 50           | 1,000          | $12/mo or $96/yr |
| Enterprise | Unlimited    | Unlimited      | Contact us   |

- **Videos**: Number of unique YouTube videos a user can load for Q&A
- **Messages**: Number of chat messages (questions) a user can send

---

## How Limits Are Enforced

### Video Limit Enforcement

When a user attempts to load a new video, the system checks their usage:

```
User Request → UsageService.enforce_video_limit(user_id)
  ├─ Check: videos_used < video_limit?
  │    ├─ Yes → Allow video load → record_video_usage()
  │    └─ No → Return 402 Payment Required
```

**Location**: `backend/app/services/usage_service.py`

```python
async def enforce_video_limit(self, user_id: UUID) -> None:
    """Raises UsageLimitExceeded if video limit reached."""
    can_load, videos_used, video_limit = await self.billing_service.check_video_limit(user_id)
    if not can_load:
        raise UsageLimitExceeded(
            message="Video limit reached for this billing period",
            resource_type="video",
            current_usage=videos_used,
            limit=video_limit,
        )
```

### Message Limit Enforcement

When a user sends a chat message:

```
User Message → UsageService.enforce_message_limit(user_id)
  ├─ Check: messages_used < message_limit?
  │    ├─ Yes → Process message → record_message_usage()
  │    └─ No → Return 402 Payment Required
```

**Location**: `backend/app/services/usage_service.py`

```python
async def enforce_message_limit(self, user_id: UUID) -> None:
    """Raises UsageLimitExceeded if message limit reached."""
    can_send, messages_used, message_limit = await self.billing_service.check_message_limit(user_id)
    if not can_send:
        raise UsageLimitExceeded(
            message="Message limit reached for this billing period",
            resource_type="message",
            current_usage=messages_used,
            limit=message_limit,
        )
```

### HTTP Response

When limits are exceeded, the API returns:

```json
HTTP 402 Payment Required
{
  "detail": {
    "message": "Video limit reached for this billing period",
    "resource_type": "video",
    "current_usage": 3,
    "limit": 3
  }
}
```

---

## Usage Tracking Database

### Table: `usage_tracking`

| Column         | Type      | Description                          |
|----------------|-----------|--------------------------------------|
| id             | UUID      | Primary key                          |
| user_id        | UUID      | Foreign key to users                 |
| videos_used    | INTEGER   | Count of videos loaded this period   |
| messages_used  | INTEGER   | Count of messages sent this period   |
| period_start   | TIMESTAMP | Start of billing period              |
| period_end     | TIMESTAMP | End of billing period                |
| created_at     | TIMESTAMP | Record creation time                 |
| updated_at     | TIMESTAMP | Last update time                     |

Each user has one active `usage_tracking` record per billing period.

---

## Monthly Reset Mechanism

### Pro Plan (Stripe-managed)

For paying customers, the billing period and usage reset is managed by Stripe:

1. **Stripe sends `invoice.paid` webhook** when subscription renews
2. **Backend receives webhook** at `/api/webhooks/stripe`
3. **`handle_invoice_paid()` is called** in `billing_service.py`
4. **Usage is reset** by creating a new `usage_tracking` record

```python
async def handle_invoice_paid(self, stripe_subscription_id: str):
    # Get new period from Stripe
    stripe_sub = await self.stripe_service.get_subscription(stripe_subscription_id)

    # Reset usage for new period
    await self.usage_repo.reset_usage(
        user_id=subscription.user_id,
        new_period_start=stripe_sub["current_period_start"],
        new_period_end=stripe_sub["current_period_end"],
    )
```

### Free Plan (Calendar-based)

For free users, the billing period follows calendar months:

- **Period Start**: First day of current month (00:00:00 UTC)
- **Period End**: First day of next month (00:00:00 UTC)

```python
# Calculate monthly period for free plan
now = datetime.now(timezone.utc)
period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
next_month = (period_start + timedelta(days=32)).replace(day=1)
period_end = next_month
```

When a free user makes a request after their period ended:
1. `get_or_create_current_usage()` checks if current period has expired
2. If expired, creates a new `usage_tracking` record with fresh counters (0, 0)
3. User gets full limits again for the new month

---

## Webhook Events for Subscription Lifecycle

| Stripe Event                     | Action                                    |
|----------------------------------|-------------------------------------------|
| `checkout.session.completed`     | Upgrade to Pro, create usage record       |
| `customer.subscription.updated`  | Update status, period dates               |
| `customer.subscription.deleted`  | Downgrade to Free                         |
| `invoice.paid`                   | Reset usage for new billing period        |
| `invoice.payment_failed`         | Log warning (Stripe handles retry)        |

**Location**: `backend/app/api/routes/webhooks.py`

---

## Frontend Display

### Header Usage Dropdown

Shows current usage vs limits:
- "3/50 Videos" or "3/Unlimited Videos"
- "45/1000 Messages" or "45/Unlimited Messages"

**Location**: `frontend/src/components/UsageDropdown.tsx`

### Billing Page

Shows detailed usage with progress bars and upgrade prompts.

**Location**: `frontend/src/pages/billing.astro`

---

## API Endpoints

| Endpoint                | Method | Description                           |
|-------------------------|--------|---------------------------------------|
| `/api/billing/status`   | GET    | Get subscription + usage combined     |
| `/api/billing/usage`    | GET    | Get current period usage only         |
| `/api/billing/plans`    | GET    | List available plans with limits      |

---

## Configuration

Limits are stored in the `subscription_plans` database table:

```sql
SELECT name, video_limit, message_limit
FROM subscription_plans
WHERE is_active = true;

-- Result:
-- name       | video_limit | message_limit
-- -----------|-------------|---------------
-- free       | 3           | 50
-- pro        | 50          | 1000
-- enterprise | NULL        | NULL  (NULL = unlimited)
```

To modify limits, update the database directly or via admin tools.

---

## Testing Limits

### Manual Testing

1. Create a free account
2. Load 3 videos (should succeed)
3. Try loading a 4th video (should get 402 error)
4. Upgrade to Pro via /pricing
5. Load more videos (should succeed up to 50)

### Automated Tests

```bash
# Run billing tests
pytest tests/unit/test_billing_service.py -v
pytest tests/unit/test_usage_service.py -v
pytest tests/integration/test_billing_api.py -v
```

---

## Troubleshooting

### "Usage limit reached" but user should have quota

1. Check `usage_tracking` table for user's current period
2. Verify `period_end` hasn't passed
3. If period expired, the next request should auto-create new record

### Pro user not getting reset

1. Check Stripe dashboard for webhook delivery status
2. Verify `STRIPE_WEBHOOK_SECRET` is correct in `.env`
3. Check backend logs for webhook processing errors

### Free user limits not resetting

1. Verify current date is past `period_end` in database
2. Make any API request to trigger new period creation
3. Check `get_or_create_current_usage()` logic in `usage_repo.py`

---

**Last Updated**: 2025-12-29
