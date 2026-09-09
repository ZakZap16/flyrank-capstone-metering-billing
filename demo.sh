#!/usr/bin/env bash
# =============================================================================
# FlyRank Capstone — 6-Minute Metering & Billing Demo
# =============================================================================
# Prerequisites:
#   1. cp .env.example .env  (fill in STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET)
#   2. docker compose up -d
#   3. uv run alembic upgrade head
#   4. uv run python seed.py
#   5. stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
#      (keep this running in a separate terminal)
# =============================================================================

set -e

API="http://localhost:8000"
TENANT_ID=$(uv run python -c "import uuid; print(uuid.uuid4())")
# NOTE: Replace with the actual tenant ID from seed.py output
# TENANT_ID="<your-seeded-tenant-id>"
IDEM_KEY=$(uv run python -c "import uuid; print(uuid.uuid4())")

echo ""
echo "============================================================"
echo "  FlyRank Metering & Billing — 6-Minute Demo"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Step 0: Verify API is up
# ---------------------------------------------------------------------------
echo "[Step 0] Health check..."
curl -sf "$API/health" | python -m json.tool || { echo "API not running. Start with: uv run uvicorn src.main:app --reload"; exit 1; }
echo "  OK — API is healthy"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Prove idempotency — same key = one event
# ---------------------------------------------------------------------------
echo "[Step 1] Idempotency test (same Idempotency-Key = one event)..."
echo "  POST /api/v1/meter — request #1..."
RES1=$(curl -s -X POST "$API/api/v1/meter" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{"usage_type": "api_call", "qty": 1}')
echo "  Response: $RES1"
EVENT1=$(echo "$RES1" | python -m json.tool 2>/dev/null | grep usage_event_id | head -1 | awk '{print $2}' | tr -d ',')

echo "  POST /api/v1/meter — request #2 (same idempotency key)..."
RES2=$(curl -s -X POST "$API/api/v1/meter" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{"usage_type": "api_call", "qty": 1}')
echo "  Response: $RES2"
EVENT2=$(echo "$RES2" | python -m json.tool 2>/dev/null | grep usage_event_id | head -1 | awk '{print $2}' | tr -d ',')

if [ "$EVENT1" = "$EVENT2" ]; then
  echo "  ✓ PASS — Same event ID returned (idempotency confirmed)"
else
  echo "  ✗ FAIL — Different event IDs returned"
  exit 1
fi
echo ""

# ---------------------------------------------------------------------------
# Step 2: Hit the quota boundary — 1 slot left, next request = 429
# ---------------------------------------------------------------------------
echo "[Step 2] Quota boundary test..."
echo "  Current usage for demo tenant (should be 4,999 / 5,000 API calls)..."
curl -s "$API/api/v1/usage" \
  -H "X-Tenant-ID: $TENANT_ID" | python -m json.tool

echo "  Making the FINAL allowed request (slot #5000)..."
FINAL_KEY=$(uv run python -c "import uuid; print(uuid.uuid4())")
curl -s -X POST "$API/api/v1/meter" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Idempotency-Key: $FINAL_KEY" \
  -d '{"usage_type": "api_call", "qty": 1}' | python -m json.tool

echo "  Making the OVER-QUOTA request (slot #5001 — should be 429)..."
OVER_KEY=$(uv run python -c "import uuid; print(uuid.uuid4())")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/api/v1/meter" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Idempotency-Key: $OVER_KEY" \
  -d '{"usage_type": "api_call", "qty": 1}')

if [ "$HTTP_CODE" = "429" ]; then
  echo "  ✓ PASS — HTTP $HTTP_CODE (Too Many Requests) — quota enforced cleanly"
else
  echo "  ? Got HTTP $HTTP_CODE — check seed data"
fi
echo ""

# ---------------------------------------------------------------------------
# Step 3: Fire Stripe webhook (stripe trigger or manual curl)
# ---------------------------------------------------------------------------
echo "[Step 3] Stripe webhook — fire checkout.session.completed"
echo "  (Requires: stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe)"
echo "  Simulating via stripe trigger..."
stripe trigger checkout.session.completed --mock 2>/dev/null || \
  echo "  Note: Install Stripe CLI and run: stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe"
echo "  Webhook endpoint: POST /api/v1/webhooks/stripe"
echo ""

# ---------------------------------------------------------------------------
# Step 4: GET /usage — prove cost rollup
# ---------------------------------------------------------------------------
echo "[Step 4] GET /api/v1/usage — cost rollup..."
curl -s "$API/api/v1/usage" \
  -H "X-Tenant-ID: $TENANT_ID" | python -m json.tool

echo ""
echo "============================================================"
echo "  Demo complete"
echo "============================================================"
echo ""
echo "Endpoints:"
echo "  POST /api/v1/meter           Record usage (requires Idempotency-Key)"
echo "  GET  /api/v1/usage           Usage rollup with cost breakdown"
echo "  POST /api/v1/auth/key       Generate API key"
echo "  POST /api/v1/checkout/session  Create Stripe checkout session"
echo "  POST /api/v1/billing/portal  Create Stripe billing portal session"
echo "  POST /api/v1/subscriptions/cancel  Cancel subscription"
echo "  POST /api/v1/webhooks/stripe Stripe webhook receiver"
echo "  GET  /health                 Health check"
echo ""
