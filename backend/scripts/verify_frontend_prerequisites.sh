#!/bin/bash

# Verify Frontend Prerequisites Script
# Tests all backend requirements needed before starting frontend development

set -e

echo "========================================="
echo "Frontend Prerequisites Verification"
echo "========================================="
echo ""

BASE_URL="http://localhost:8000"
PASSED=0
FAILED=0

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
test_passed() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

test_failed() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

test_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Test 1: Backend API is running
echo "1. Testing backend API availability..."
if curl -s -f "$BASE_URL/api/health" > /dev/null; then
    test_passed "Backend API running on $BASE_URL"
else
    test_failed "Backend API not accessible at $BASE_URL"
    echo "   Please start the backend: cd backend && uvicorn app.main:app --reload"
    exit 1
fi

# Test 2: Health endpoint
echo "2. Testing /api/health endpoint..."
HEALTH_RESPONSE=$(curl -s "$BASE_URL/api/health")
if echo "$HEALTH_RESPONSE" | grep -q '"status".*"ok"'; then
    test_passed "Health endpoint returns OK"
else
    test_failed "Health endpoint not returning expected response"
fi

# Test 3: Database health check
echo "3. Testing /api/health/db endpoint..."
DB_HEALTH=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/api/health/db")
if [ "$DB_HEALTH" = "200" ]; then
    test_passed "Database health check passed"
else
    test_failed "Database health check failed (HTTP $DB_HEALTH)"
fi

# Test 4: Qdrant health check
echo "4. Testing /api/health/qdrant endpoint..."
QDRANT_HEALTH=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/api/health/qdrant")
if [ "$QDRANT_HEALTH" = "200" ]; then
    test_passed "Qdrant health check passed"
else
    test_failed "Qdrant health check failed (HTTP $QDRANT_HEALTH)"
fi

# Test 5: Auth endpoints exist
echo "5. Testing auth endpoints..."

# Test register endpoint (should return 422 for missing body)
REGISTER_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/api/auth/register")
if [ "$REGISTER_STATUS" = "422" ]; then
    test_passed "Register endpoint exists (/api/auth/register)"
else
    test_warning "Register endpoint returned unexpected status: $REGISTER_STATUS"
fi

# Test login endpoint (should return 422 for missing body)
LOGIN_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/api/auth/login")
if [ "$LOGIN_STATUS" = "422" ]; then
    test_passed "Login endpoint exists (/api/auth/login)"
else
    test_warning "Login endpoint returned unexpected status: $LOGIN_STATUS"
fi

# Test 6: WebSocket endpoint exists
echo "6. Testing WebSocket endpoint..."
# WebSocket endpoints can't be tested with curl easily, but we can check if it's registered
WS_TEST=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/api/ws/chat")
if [ "$WS_TEST" = "400" ] || [ "$WS_TEST" = "426" ]; then
    test_passed "WebSocket endpoint exists (/api/ws/chat)"
else
    test_warning "WebSocket endpoint test inconclusive (HTTP $WS_TEST)"
fi

# Test 7: API documentation
echo "7. Testing API documentation..."
DOCS_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/docs")
if [ "$DOCS_STATUS" = "200" ]; then
    test_passed "API documentation available at $BASE_URL/docs"
else
    test_failed "API documentation not accessible"
fi

# Test 8: Conversations endpoint (requires auth, should return 403/401)
echo "8. Testing conversations endpoint..."
CONV_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/api/conversations")
if [ "$CONV_STATUS" = "403" ] || [ "$CONV_STATUS" = "401" ]; then
    test_passed "Conversations endpoint exists (requires auth)"
else
    test_warning "Conversations endpoint returned unexpected status: $CONV_STATUS"
fi

# Summary
echo ""
echo "========================================="
echo "Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All prerequisites met!${NC}"
    echo ""
    echo "Backend is ready for frontend development."
    echo ""
    echo "Next steps:"
    echo "1. Review PROJECT_FLOW_DOCS/HANDOFF_FRONT.md"
    echo "2. Create frontend/ directory"
    echo "3. Initialize Astro project"
    echo ""
    echo "API Documentation: $BASE_URL/docs"
    exit 0
else
    echo -e "${RED}✗ Some prerequisites failed${NC}"
    echo "Please fix the failed checks before proceeding."
    exit 1
fi
