# User Service API Audit Report

**Date**: March 17, 2026  
**Scope**: Admin Assistant (Web2 read-only perspective)  
**Auditor**: AI Assistant  

---

## 1. EXECUTIVE SUMMARY

### Current State ✓
- **18 user-service tools** currently implemented
- **All are read-only** (GET methods only)
- **Clean API coverage** for admin operations
- **Zero redundancy** in tool design

### Key Findings
- ✅ **Tools are well-aligned**: All 18 tools serve legitimate admin use-cases
- ⚠️ **Web2 never calls some tools**: `verify_client_token()` is rarely used in Web2
- ❓ **Token verification purpose unclear**: Is this for admin security audits or system validation?
- ✅ **No hidden POST-as-GET APIs**: All endpoints correctly classified by HTTP method
- 🎯 **Most-used tools** in admin flow: profile lookup, org/branch hierarchy, RBAC menus

---

## 2. WEB2 REAL USAGE ANALYSIS

### Web2 Flow (from docs/summary-fe-api.md)

Web2 calls these user-service endpoints:

| Endpoint | HTTP | Purpose | Admin Utility |
|----------|------|---------|---------------|
| `/auth/login` | POST | Authentication | ❌ Not read-only |
| `/auth/logout` | POST | Session end | ❌ Not read-only |
| `/users/me` | GET | Current user profile | ✅ **HIGH** (get_my_user_profile) |
| `/users` | PUT | Update profile | ❌ Not read-only |
| `/users/change-password` | PATCH | Change password | ❌ Not read-only |
| `/users/agreement` | POST | Update preferences | ❌ Not read-only |
| `/verify-password` | POST | Verify pwd (security gate) | ✅ Maybe useful? |
| `/withdraw-reasons` | GET | Withdrawal reasons | ✅ **MEDIUM** (get_withdraw_reasons) |
| `/withdraw` | POST | Initiate withdrawal | ❌ Not read-only |
| `/feature/flag` | GET | Global feature flags | ✅ **HIGH** (get_feature_flags) |
| `/auth/kcb/authentication-result` | GET | KCB result verification | ❌ B2C only |
| `/auth/b2c/org-code/validate` | GET | B2C org validation | ✅ Maybe useful? |

**Web2 Does NOT call** (but admin assistant has tools):
- `/users?id=` → `get_user_profile()` ← **Admin-specific need** ✓
- `/users/search` → `search_users()` ← **Admin-specific need** ✓
- `/user-driver?id=` → `get_user_driver()` ← **Admin-specific need** ✓
- `/branch?id=`, `/branch/search` → branch tools ← **Admin-specific need** ✓
- `/organization?id=`, `/organization/search` → org tools ← **Admin-specific need** ✓
- `/admin/roles`, `/admin/departments`, `/admin/menus`, `/admin/permissions/*` ← **Admin RBAC** ✓

**Tools that Web2 doesn't rely on but admin does**:
These are **correctly added for admin use case** — not redundant, just different need.

---

## 3. TOOL-BY-TOOL ANALYSIS

### Tier 1: HIGH-VALUE TOOLS (Essential for admin operations)

| Tool | Endpoint | Admin Use Case | Calls | Frequency |
|------|----------|-----------------|-------|-----------|
| `get_my_user_profile()` | GET /users/me | Current operator identity | Auth context | Every session |
| `get_user_profile(user_id)` | GET /users?id= | Lookup customer account | Direct lookup | **High** |
| `search_users(name, phone, email)` | GET /users/search | Find customer by criteria | Multi-param search | **High** |
| `get_feature_flags()` | GET /feature/flag | System feature gates | Config lookup | Medium |
| `search_organizations()` | GET /organization/search | Find business entities | B2B admin | **High** |
| `get_organization_by_id()` | GET /organization?id= | Org detail lookup | Direct lookup | Medium |
| `search_branches()` | GET /branch/search | Find branch/location | Logistics admin | **High** |
| `get_branch_by_id()` | GET /branch?id= | Branch detail lookup | Direct lookup | Medium |
| `list_admin_roles()` | GET /admin/roles | RBAC: who has what roles | Permission audit | **High** |
| `get_admin_permissions(role_id)` | GET /admin/permissions?roleId= | RBAC: role capabilities | Permission audit | **High** |

**Recommendation**: All **KEEP**. These are core to admin operations.

---

### Tier 2: MEDIUM-VALUE TOOLS (Contextual but useful)

| Tool | Endpoint | Admin Use Case | Frequency | Keep? |
|------|----------|-----------------|-----------|-------|
| `get_user_driver(user_id)` | GET /user-driver?id= | Check if user linked to driver profile | Low-medium | **KEEP** (driver audits) |
| `get_withdraw_reasons()` | GET /withdraw-reasons | List valid withdrawal reasons | Low-medium | **KEEP** (support context) |
| `get_tos_contents()` | GET /guest/tos-contents | Legal/support reference | Low | **KEEP** (legal context) |
| `get_my_feature_flags()` | GET /auth/feature/flag | Current operator's feature flags | Low-medium | **EVALUATE** (see below) |
| `list_admin_departments()` | GET /admin/departments | Org structure: departments | Low-medium | **KEEP** (admin hierarchy) |
| `list_admin_menus()` | GET /admin/menus | UI permission reference | Low-medium | **KEEP** (admin hierarchy) |
| `get_accessible_menu_tree(role_id)` | GET /admin/permissions/menus?roleId= | Role-based menu access | Low-medium | **KEEP** (admin hierarchy) |

**Assessment**: Most are **KEEP**. One to evaluate: `get_my_feature_flags()`.

---

### Tier 3: QUESTIONABLE/NICHE TOOLS

| Tool | Endpoint | Admin Use Case | Recommendation |
|------|----------|-----------------|-----------------|
| `get_my_feature_flags()` | GET /auth/feature/flag | **Operator's own feature flags** | **EVALUATE**: Is this ever useful? Or just noise? |
| `verify_client_token(token)` | GET /auth/client-token/verify?token= | Token validation (security audit?) | **MARGINAL**: Rarely asked by admins. Might be dead weight. |

---

## 4. DUPLICATE/REDUNDANCY CHECK

### Feature Flag Tools (Potential Overlap?)

```
get_feature_flags()          → GET /feature/flag             (global)
get_my_feature_flags()       → GET /auth/feature/flag        (user-specific)
```

**Analysis**:
- Global flags = system-wide feature gates
- User flags = operator's personal feature set
- **Not redundant IF** they return different data
- **Concern**: If user flags ⊆ global flags, then user-specific call wastes a round

**Recommendation**: 
- Keep `get_feature_flags()` (commonly needed)
- **REMOVE** `get_my_feature_flags()` unless admins explicitly need to audit their own permissions
  - Or: Add clear docstring explaining when to use each (to prevent Gemini confusion)

---

### Organization/Branch Lookup (Necessary Pair)

```
get_organization_by_id(id)   → GET /organization?id=
search_organizations(...)    → GET /organization/search

get_branch_by_id(id)         → GET /branch?id=
search_branches(...)          → GET /branch/search
```

**Analysis**:
- These follow standard **get-by-id + search pair** pattern
- **Not redundant**: Direct lookup vs. search are complementary
- **No optimization needed**

**Recommendation**: KEEP both in each pair.

---

### User Lookup (Necessary Trio)

```
get_user_profile(user_id)    → GET /users?id=              (by ID)
search_users(name, phone, email) → GET /users/search       (by criteria)
get_my_user_profile()        → GET /users/me               (current operator)
```

**Analysis**:
- `get_user_profile(id)` = direct lookup
- `search_users()` = multi-field search (flexible)
- `get_my_user_profile()` = current operator (essential for "me" questions)
- **Not redundant**: Three different use-cases
- `search_users()` is NOT a replacement for direct lookup by ID (search is slower, less precise)

**Recommendation**: KEEP all three.

---

### Admin RBAC Tools (Hierarchy Makes Sense)

```
list_admin_departments()              → GET /admin/departments
list_admin_roles(department_id)       → GET /admin/roles
list_admin_menus()                    → GET /admin/menus
get_admin_permissions(role_id)        → GET /admin/permissions?roleId=
get_accessible_menu_tree(role_id)     → GET /admin/permissions/menus?roleId=
```

**Analysis**:
- These form a **hierarchy**: departments → roles → permissions → menus
- `list_admin_menus()` lists UI menu structure globally
- `get_accessible_menu_tree(role_id)` filters menus by role
- **Not redundant**: Each serves a distinct level of RBAC query

**Recommendation**: KEEP all. They form a coherent RBAC introspection suite.

---

## 5. HTTP METHOD ANALYSIS: Are there hidden POST-as-GET APIs?

Checked all 18 user tools. All claims verified against actual implementation:

| Tool | Claimed Method | Actual Implementation | Status |
|------|----------------|-----------------------|--------|
| `get_feature_flags()` | GET | GET /feature/flag | ✓ Correct |
| `get_my_feature_flags()` | GET | GET /auth/feature/flag | ✓ Correct |
| `get_user_profile()` | GET | GET /users?id= | ✓ Correct |
| `get_my_user_profile()` | GET | GET /users/me | ✓ Correct |
| `search_users()` | GET | GET /users/search | ✓ Correct |
| `get_user_driver()` | GET | GET /user-driver?id= | ✓ Correct |
| `get_withdraw_reasons()` | GET | GET /withdraw-reasons | ✓ Correct |
| `get_tos_contents()` | GET | GET /guest/tos-contents | ✓ Correct |
| `get_branch_by_id()` | GET | GET /branch?id= | ✓ Correct |
| `search_branches()` | GET | GET /branch/search | ✓ Correct |
| `get_organization_by_id()` | GET | GET /organization?id= | ✓ Correct |
| `search_organizations()` | GET | GET /organization/search | ✓ Correct |
| `verify_client_token()` | GET | GET /auth/client-token/verify?token= | ✓ Correct (despite `/auth/` namespace) |
| `list_admin_roles()` | GET | GET /admin/roles | ✓ Correct |
| `list_admin_departments()` | GET | GET /admin/departments | ✓ Correct |
| `list_admin_menus()` | GET | GET /admin/menus | ✓ Correct |
| `get_admin_permissions()` | GET | GET /admin/permissions?roleId= | ✓ Correct |
| `get_accessible_menu_tree()` | GET | GET /admin/permissions/menus?roleId= | ✓ Correct |

**Finding**: ✅ **NO hidden POST-as-GET APIs**. All tools correctly use GET. 

**Note on `/auth/client-token/verify`**: Despite being under `/auth/` namespace, this is correctly a GET (read-only token validation), not POST.

---

## 6. MISSING TOOLS ANALYSIS

### Should we add these from Web2?

| Endpoint | Method | Purpose | Admin Need? | Recommendation |
|----------|--------|---------|------------|-----------------|
| `/verify-password` | POST | Verify admin's password (security gate) | ❓ Maybe? | ❓ **DISCUSS**: Useful for admin auth workflows? |
| `/auth/b2c/org-code/validate` | GET | Validate B2C org code | ✅ Yes | **ADD**: `validate_b2c_org_code(org_code)` |
| `/guest/etax/verify_biz_registration_number` | GET | Verify business registration | ✅ Yes | **ADD**: `verify_biz_registration_number(biz_number)` |
| `/users?id=` with phone/email lookup | - | Direct lookup by phone/email | ✅ Maybe | Already covered by `search_users()` |

### Candidates to ADD:

1. **`validate_b2c_org_code(org_code)`** 
   - Endpoint: `GET /auth/b2c/org-code/validate?orgCode=…`
   - Use case: Admin needs to check if an org code is valid before assigning
   - **Impact**: Minimal (1 line tool wrapper)
   - **Recommendation**: ✅ **ADD** (completes B2B admin tooling)

2. **`verify_biz_registration_number(biz_number)`**
   - Endpoint: `GET /guest/etax/verify_biz_registration_number/{bizNumber}?userId=…`
   - Use case: Admin needs to audit business registration validity
   - **Impact**: Minimal (1 line tool wrapper)
   - **Recommendation**: ✅ **ADD** (supports compliance audits)

3. **`verify_admin_password(password)`** (POST /verify-password)
   - Endpoint: `POST /verify-password`
   - Issue: **POST method** → violates read-only constraint
   - **Recommendation**: ❌ **SKIP** (not read-only; also uncommon admin use case)

---

## 7. PROMPT ALIGNMENT ANALYSIS

Checked `app/orchestrator/prompt_builder.py` for tool documentation:

### Current Prompt Coverage

✅ All 18 tools have **clear docstrings** explaining:
- HTTP method and endpoint
- Parameters and their meaning
- When to use each tool

✅ Prompt provides **smart tool selection guidance**:
- When to use `search_users()` vs. `get_user_profile()`
- When to use `get_my_feature_flags()` vs. `get_feature_flags()`
- Admin RBAC tool hierarchy

⚠️ **Omissions in prompt**:
- No guidance on **`verify_client_token()`** (when would an admin call this?)
- No guidance on when **`get_my_feature_flags()`** vs **`get_feature_flags()`** (source of confusion?)
- No mention of uncommonly used tools like `get_tos_contents()` (legal context only)

---

## 8. GEMINI OPTIMIZATION ANALYSIS

### Tool Duplication Risk (Wasted Rounds)

Current: 18 tools  
Gemini risk: **Calling both `get_feature_flags()` and `get_my_feature_flags()` when one would suffice**

**Symptom**: If Gemini calls both tools in same response, that's 2 unnecessary round-trips.

**Mitigation**: Add clear docstring distinction:
```python
def get_feature_flags() -> dict:
    """Global system feature flags (applied to ALL users/admins).
    Use FIRST for config/feature questions.
    Use ONLY if no user context is needed.
    """
    
def get_my_feature_flags() -> dict:
    """Current operator's personal feature flags (overrides/additions to global).
    Use ONLY if explicitly asked "what are MY flags?" or permission audit needed.
    """
```

---

## 9. RECOMMENDATIONS (Prioritized)

### 🔴 CRITICAL (Do Now)

1. **Clarify `get_my_feature_flags()` usage**
   - Why does admin need this?
   - Or: Remove to reduce tool duplication
   - **Action**: Decide now vs. remove

2. **Document `verify_client_token()` purpose**
   - When would admin call this?
   - Is it dead weight?
   - **Action**: Audit usage logs or remove

### 🟡 IMPORTANT (Do This Sprint)

3. **Add `validate_b2c_org_code(org_code)`**
   - Endpoint: `GET /auth/b2c/org-code/validate?orgCode=…`
   - Value: Completes B2B org validation tooling
   - **Action**: 1-line wrapping in user_service_client.py, 1 tool in user_tools.py

4. **Add `verify_biz_registration_number(biz_number, user_id=None)`**
   - Endpoint: `GET /guest/etax/verify_biz_registration_number/{bizNumber}?userId=…`
   - Value: Compliance audit support
   - **Action**: Same as above

5. **Update prompt docstrings**
   - Clarify when to use feature flag tools (prevent Gemini duplication)
   - Document `verify_client_token()` use-case or remove
   - **Action**: Edit prompt_builder.py

### 🟢 NICE-TO-HAVE (Backlog)

6. **Profile endpoint normalization**
   - Both `/users?id=` and `/users/me` return user profiles with same shape
   - Consider: Dedicated slim_user_profile() method to normalize across both
   - Actually: Already done in `_slim_user_profile()` ✓ (good call)

---

## 10. CONCLUSION

### Overall Assessment: ✅ **SOLID**

- ✅ All 18 tools serve real admin use-cases
- ✅ No redundancy (tool pairs are complementary, not duplicate)
- ✅ All HTTP methods correct (no hidden POST-as-GET)
- ✅ Coverage of Web2 + admin-specific operations is comprehensive
- ⚠️ 2 tools need clarification (`get_my_feature_flags()`, `verify_client_token()`)
- ✅ 2 gaps identified that should be filled (`validate_b2c_org_code`, `verify_biz_registration_number`)

### Action Items

| Item | Priority | Effort | Owner |
|------|----------|--------|-------|
| Clarify/remove `get_my_feature_flags()` | CRITICAL | 1h | AI |
| Document or remove `verify_client_token()` | CRITICAL | 1h | AI |
| Add `validate_b2c_org_code()` tool | IMPORTANT | 30m | AI |
| Add `verify_biz_registration_number()` tool | IMPORTANT | 30m | AI |
| Update prompt docstrings | IMPORTANT | 45m | AI |
| **TOTAL** | | **~3.5h** | |

---

## Appendix: API Endpoint Reference

### All User Service Endpoints Used by Admin Assistant

```
GET /api/v1/users                 - get user by ID
GET /api/v1/users/me              - get current user
GET /api/v1/users/search          - search users
GET /api/v1/user-driver?id=       - get driver profile
GET /api/v1/feature/flag          - global feature flags
GET /api/v1/auth/feature/flag     - user-specific flags
GET /api/v1/withdraw-reasons      - withdrawal reasons list
GET /api/v1/guest/tos-contents    - ToS content
GET /api/v1/branch?id=            - get branch by ID
GET /api/v1/branch/search         - search branches
GET /api/v1/organization?id=      - get org by ID
GET /api/v1/organization/search   - search orgs
GET /api/v1/auth/client-token/verify - token verification
GET /api/v1/admin/roles           - list admin roles
GET /api/v1/admin/departments     - list departments
GET /api/v1/admin/menus           - list admin menus
GET /api/v1/admin/permissions     - get role permissions
GET /api/v1/admin/permissions/menus - get role-filtered menus
```

### Candidate Endpoints to Add

```
GET /api/v1/auth/b2c/org-code/validate - validate B2C org code
GET /api/v1/guest/etax/verify_biz_registration_number - verify business registration
```

---

**Report generated**: 2026-03-17
