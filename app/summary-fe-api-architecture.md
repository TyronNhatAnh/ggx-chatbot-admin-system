# Frontend API Architecture — `ggx-kr-consumer-web`

> **Purpose:** Documents how backend API calls are organized in this Next.js codebase. Used as a reference for automated scanner design and codebase onboarding.

---

## Table of Contents

1. [Folder Structure](#1-folder-structure)
2. [HTTP Client Layer](#2-http-client-layer)
3. [Service Layer (API Modules)](#3-service-layer-api-modules)
4. [Endpoint Definitions](#4-endpoint-definitions)
5. [Data Flow](#5-data-flow)
6. [State Management Integration](#6-state-management-integration)
7. [Next.js API Routes](#7-nextjs-api-routes)
8. [Environment Variables](#8-environment-variables)
9. [API Call Patterns — Scanner Reference](#9-api-call-patterns--scanner-reference)

---

## 1. Folder Structure

```
src/
├── app/
│   └── api/                          ← Next.js App Router API routes (health + dev util only)
│       ├── healthz/route.ts
│       └── set_contry_code/route.ts
├── pages/                            ← All UI pages (Pages Router)
│   ├── orders/[id].tsx
│   ├── dashboard/
│   ├── login/, signup/, user/
│   └── public/
├── middleware.ts                     ← Edge middleware (domain-based rewrites only)
└── lib/
    ├── apis/                         ← ★ API service layer (all backend calls defined here)
    │   ├── order.ts                  ← OrderAPIs
    │   ├── user.ts                   ← UserAPIs
    │   ├── common.ts                 ← CommonAPIs
    │   ├── notify.ts                 ← NotifyAPIs
    │   ├── notification.ts           ← NotificationAPIs
    │   └── driver.ts                 ← DriverAPIs
    ├── common/
    │   ├── constants/                ← Enums, configs, path constants
    │   ├── helpers/
    │   │   └── axios/                ← ★ HTTP client factory + interceptors
    │   │       ├── index.ts          ← makeAxiosClient() + 8 named client exports
    │   │       └── interceptors/
    │   │           ├── index.ts      ← Interceptor registry
    │   │           ├── auth.ts       ← Auth headers + 401 logout
    │   │           ├── tracking.ts   ← Loading state + request counter
    │   │           └── response-parser.ts ← Unwraps AxiosResponse envelope
    │   ├── hooks/                    ← Custom React hooks
    │   └── hoc/
    │       ├── with-app-store.tsx    ← Bootstrap: wires interceptors to Redux store
    │       └── with-swr.tsx          ← Global SWR config
    ├── containers/                   ← Feature containers (call API modules + dispatch thunks)
    └── ducks/                        ← ★ Redux Toolkit: store, slices, thunks
        └── reducers/
            ├── auth/thunks.ts        ← login, logout, getProfile, updateProfile
            ├── order/thunks.ts       ← createOrder
            ├── app/slice.ts          ← global loading, error state
            └── signup/slice.ts
```

**Key TypeScript path aliases** (`tsconfig.json`):

| Alias | Resolves to |
|---|---|
| `@apis/*` | `src/lib/apis/*` |
| `@helpers/*` | `src/lib/common/helpers/*` |
| `@ducks/*` | `src/lib/ducks/*` |
| `@constants/*` | `src/lib/common/constants/*` |
| `@hooks/*` | `src/lib/common/hooks/*` |

---

## 2. HTTP Client Layer

**File:** `src/lib/common/helpers/axios/index.ts`

### Factory Pattern

A single `makeAxiosClient(basePath?)` factory creates all HTTP clients:

```ts
const configs: AxiosRequestConfig = {
    baseURL: "/",
    headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    },
    timeout: 60000,
};

function makeAxiosClient(basePath?: string) {
    const baseURL = basePath
        && `${process.env.NEXT_PUBLIC_BACKEND_API_URL || ""}${basePath}`;
    return axios.create({ ...configs, baseURL }) as KwcAxiosInstance;
}
```

### Named Axios Instances (8 total)

| Export name | Base URL |
|---|---|
| `userServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/user/api/v1` |
| `orderServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/order/api/v1` |
| `commonServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/common/api/v1` |
| `notifyServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/notification/api/v1` |
| `notificationServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/notification/api/v1` |
| `driverServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/driver/api/v1` |
| `driverDAServiceApiClient` | `{NEXT_PUBLIC_BACKEND_API_URL}/da-api/guest/driver` |
| `axiosClient` (default) | `/` (no base path; used for absolute URLs) |

### Interceptors

Three interceptors are applied to **all 8 clients** during app bootstrap (`with-app-store.tsx`):

| File | Phase | Behavior |
|---|---|---|
| `interceptors/tracking.ts` | Request + Response | Counts in-flight requests; dispatches `setAppLoading` and `setPendingRequestCount` to Redux |
| `interceptors/auth.ts` | Request + Response | Injects `X-Platform: web2app`, `X-Request-Id` (UUID v7), `Authorization: Bearer <token>`, `withCredentials: true`; on 401 (non-profile) dispatches `logout()` |
| `interceptors/response-parser.ts` | Response | Unwraps `AxiosResponse` — callers receive `response.data` directly; rejects with `error.response.data` |

**Bootstrap sequence:**

```ts
// src/lib/common/hoc/with-app-store.tsx
function bootstrappingReduxStore() {
    const result = setupStore();
    setup(result.store);  // wires all interceptors to the Redux store
    return result;
}
```

---

## 3. Service Layer (API Modules)

All API modules live in `src/lib/apis/`. The naming convention is `*APIs` (object literal of methods), **not** `*Service` or `*Repository`.

---

### `OrderAPIs` — `src/lib/apis/order.ts`

Uses `orderServiceApiClient` → base: `/order/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `estimate(params)` | POST | `/guest/estimate` or `/guest/home-moving/estimate` |
| `createOrder(params)` | POST | `/orders` or `/home-moving/orders` |
| `getOrders(params)` | GET | `/orders` |
| `getRecentAddresses(params)` | GET | `/orders/shipping-records?keyword=…` |
| `cancelOrder(id)` | POST | `/orders/${id}/b2c-cancel` |
| `getOrder(id)` | GET | `/orders/${id}` |
| `addImage({orderId})` | POST | `/orders/${orderId}/images` |
| `addOrderTip(payload)` | POST | `/orders/${id}/submit-tip` |
| `getOrderStatistics(path)` | GET | `/orders/statistics` |
| `getPresignedUploadInfo(fileName)` | POST | `/file/presigned` |
| `getPublicOrder(params)` | GET | `/guest/orders/${organizationId}/${orderId}` |
| `getMobisPublicOrder(params)` | GET | `/guest/mobis/orders/${orderId}` |
| `coupons(orderType, paymentType)` | GET | `/coupons` |
| `paymentStatus(orderId)` | GET | `/orders/${orderId}/status` |
| `getRoute(orderId)` | GET | `/orders/${orderId}/route` |
| `getRouteNoLogin(orderId)` | GET | `guest/orders/route/${orderId}` |
| `getReorderRequestInfo(orderId)` | GET | `/orders/${orderId}/reorder` |
| `registerCoupon(couponCode)` | POST | `/coupons/register-user` |
| `hashOrderId(orderId)` | GET | `/guest/etax/hash-order/${orderId}` |
| `validateAndGetETaxOrder(orderId)` | GET | `/guest/etax/get-order/${orderId}` |
| `verifyBizRegistrationNumber(bizNumber, userId?)` | GET | `/guest/etax/verify_biz_registration_number/${bizNumber}?userId=…` |
| `createIssueTaxInvoice(payload)` | POST | `/guest/etax/issue_tax_invoice` |

---

### `UserAPIs` — `src/lib/apis/user.ts`

Uses `userServiceApiClient` → base: `/user/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `signup(payload)` | POST | `/auth/signup` or `/auth/signup-third-party` |
| `login(payload)` | POST | `/auth/login`, `/auth/login-by-kakao`, `/auth/login-by-google`, `/auth/login-by-naver` |
| `resetPassword(payload)` | POST | `/auth/reset-password` |
| `profile()` | GET | `/users/me` |
| `updateProfile(name)` | PUT | `/users` |
| `logout()` | POST | `/auth/logout` |
| `getOptByPhoneNumber(payload)` | POST | `/auth/forgot-password` |
| `changePassword(payload)` | PATCH | `/users/change-password` |
| `changeReception(payload)` | POST | `/users/agreement` |
| `verifyPassword(payload)` | POST | `/verify-password` |
| `getReasons()` | GET | `/withdraw-reasons` |
| `withdraw(payload)` | POST | `/withdraw` |
| `getKCBResult(registerToken, userId?)` | GET | `/auth/kcb/authentication-result?register_token=…` |
| `featureFlags()` | GET | `/feature/flag` |
| `validateOrgCode(orgCode)` | GET | `/auth/b2c/org-code/validate?orgCode=…` |

Also exported:
```ts
export const KCB_START_URL =
    `${process.env.NEXT_PUBLIC_BACKEND_API_URL}/user/api/v1/auth/kcb/authentication-start`;
// Used as a browser redirect target (not an axios call)
```

---

### `CommonAPIs` — `src/lib/apis/common.ts`

Uses `commonServiceApiClient` → base: `/common/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `vehicles(params?)` | GET | `/vehicles` |
| `goodsByVehicle({vehiclePoolId})` | GET | `/vehicles/${vehiclePoolId}/goods/0` |
| `homeMovingGoods()` | GET | `guest/home-moving/goods` |
| `addressSearch(params)` | GET | `/addresses/search` |
| `addressSearchDetails(params)` | GET | `/addresses/search-details` |
| `getVehicleService(params)` | GET | `/vehicles/services` |
| `getSavedAddresses(params)` | GET | `/addresses?keyword=…` |
| `deleteSavedAddress(addressId)` | DELETE | `/addresses/${addressId}` |

---

### `NotifyAPIs` — `src/lib/apis/notify.ts`

Uses `notifyServiceApiClient` → base: `/notification/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `sendSms(payload)` | POST | `/guest/otp/send-sms` |
| `sendEmail(email)` | POST | `/guest/otp/send-email` |
| `verifyOtp(payload)` | POST | `/guest/otp/verify` |

---

### `NotificationAPIs` — `src/lib/apis/notification.ts`

Uses `notificationServiceApiClient` → base: `/notification/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `saveCustomerToken(token)` | POST | `/firebase/customer/token` |

---

### `DriverAPIs` — `src/lib/apis/driver.ts`

Uses `userServiceApiClient` (reuses the user client) → base: `/user/api/v1`

| Method | HTTP | Endpoint |
|---|---|---|
| `updateDriverInfor(payload)` | POST | `/guest/etax/driver-info` |

---

## 4. Endpoint Definitions

There is **no centralized endpoint constants file** (no `API_ENDPOINTS` object or `ENDPOINTS` map). Endpoint path strings are defined **inline** inside each API module method.

The only **named endpoint constants** are:

| Constant | File | Value |
|---|---|---|
| `PROFILE_API_URL` | `src/lib/common/helpers/axios/interceptors/auth.ts` | `"/users/me"` |
| `KCB_START_URL` | `src/lib/apis/user.ts` | `${NEXT_PUBLIC_BACKEND_API_URL}/user/api/v1/auth/kcb/authentication-start` |

One endpoint is called via **server-side `fetch()`** (not axios):

```ts
// src/lib/common/helpers/get-html-term-content.ts — used in getStaticProps
const res = await fetch(
    `${process.env.BACKEND_API_URL}/user/api/v1/guest/tos-contents`
);
```

---

## 5. Data Flow

### Architecture Overview

```
Page / Container
    │
    ├─── SWR hook (reads)          ──→  API Module (src/lib/apis/*.ts)
    │        useSWR / useSWRInfinite        │
    │        useSWRImmutable                ↓
    │                               Named Axios Client
    │                               (src/lib/common/helpers/axios/index.ts)
    │                                       │
    ├─── Redux dispatch (mutations)          │  Interceptors:
    │        createAsyncThunk               │   1. Tracker (loading state)
    │        → API Module                   │   2. Auth (headers, 401 logout)
    │                                       │   3. ResponseParser (unwrap)
    └─── Direct useEffect call              ↓
             → API Module          NEXT_PUBLIC_BACKEND_API_URL
                                   + service base path
                                   + endpoint path string
                                           │
                                           ↓
                               Backend microservice
```

---

### Traced Example 1: Order Detail (SWR read)

**Page** → `src/pages/orders/[id].tsx`
```tsx
const { data, isLoading, mutate } = useSWR(
    () => orderId,
    (id) => OrderAPIs.getOrder(id),
    { shouldRetryOnError: false }
);
```

**API Module** → `src/lib/apis/order.ts`
```ts
getOrder(id: number) {
    return orderServiceApiClient.get<OrderDetail>(`/orders/${id}`);
}
```

**Resolved URL:**
```
GET https://stag-api.gogox.co.kr/order/api/v1/orders/12345
```

**Headers injected by interceptors:**
```
Authorization: Bearer <token>
X-Platform: web2app
X-Request-Id: <uuid-v7>
Content-Type: application/json
```

**Response:** `ResponseParser` unwraps `response.data` → SWR cache → component render.

---

### Traced Example 2: Login (Redux thunk)

**Container** → `src/lib/containers/b2c/auth/login.tsx`
```ts
const result = await dispatch(login({ ...payload, typeCd: USER_TYPE_CD.B2C }));
```

**Thunk** → `src/lib/ducks/reducers/auth/thunks.ts`
```ts
export const login = createAppAsyncThunk("auth/login", async (payload, { rejectWithValue }) => {
    try {
        return await UserAPIs.login(payload);
    } catch (err) {
        return rejectWithValue(err);
    }
});
```

**API Module** → `src/lib/apis/user.ts`
```ts
login(payload) {
    return userServiceApiClient.post<UserSession>("/auth/login", payload);
}
```

**Resolved URL:**
```
POST https://stag-api.gogox.co.kr/user/api/v1/auth/login
```

---

## 6. State Management Integration

The codebase uses **two complementary patterns**:

| Pattern | Purpose | Files |
|---|---|---|
| **SWR** (`useSWR`, `useSWRInfinite`, `useSWRImmutable`) | Server data reads; cache + revalidation | `src/lib/containers/**` |
| **Redux Toolkit** (`createAsyncThunk`) | Mutations and auth state | `src/lib/ducks/reducers/*/thunks.ts` |

### SWR Usage Examples

```ts
// Read + cache order list with infinite scroll
useSWRInfinite(
    (index) => ({ ...params, pageIndex: index + 1 }),
    (args) => OrderAPIs.getOrders(args)
);

// Immutable (fetch-once) estimate
useSWRImmutable(
    `estimate/${JSON.stringify(params)}`,
    () => OrderAPIs.estimate(params)
);

// User profile
useSWR("/users/me", () => UserAPIs.profile());
```

**Global SWR config** (`src/lib/common/hoc/with-swr.tsx`):
```tsx
<SWRConfig value={{ errorRetryCount: 3, revalidateOnFocus: false }}>
```

### Redux Thunks

All mutations go through `createAppAsyncThunk` (a typed wrapper around RTK's `createAsyncThunk`):

```ts
// Auth thunks (src/lib/ducks/reducers/auth/thunks.ts)
export const login         = createAppAsyncThunk("auth/login",         (p) => UserAPIs.login(p));
export const getProfile    = createAppAsyncThunk("auth/getProfile",    ()  => UserAPIs.profile());
export const updateProfile = createAppAsyncThunk("auth/updateProfile", ...);
export const logout        = createAppAsyncThunk("/auth/logout",       ...);

// Order thunks (src/lib/ducks/reducers/order/thunks.ts)
export const createOrder   = createAppAsyncThunk("order/create",       (p) => OrderAPIs.createOrder(p));
```

### Redux Slices

| Slice | File | Purpose |
|---|---|---|
| `auth` | `src/lib/ducks/reducers/auth/slice.ts` | Authenticated user state |
| `order` | `src/lib/ducks/reducers/order/slice.ts` | Draft order being placed |
| `app` | `src/lib/ducks/reducers/app/slice.ts` | Global loading, error messages |
| `signup` | `src/lib/ducks/reducers/signup/slice.ts` | Draft signup form state |

---

## 7. Next.js API Routes

There are **only 2 App Router API route handlers**. Neither acts as a BFF proxy to the backend.

| Route | File | Purpose |
|---|---|---|
| `GET /api/healthz` | `src/app/api/healthz/route.ts` | Liveness probe — returns `"OK"` |
| `GET /api/set_contry_code` | `src/app/api/set_contry_code/route.ts` | Dev-only tool to set `localStorage["MOCKED_COUNTRY_CODE"]` |

**All backend API calls go directly from the browser to `NEXT_PUBLIC_BACKEND_API_URL` via axios.** There are no BFF proxies.

The `src/middleware.ts` only rewrites Mobis subdomain requests to `/public/mobis/` page routes — it does not proxy backend calls.

---

## 8. Environment Variables

| Variable | Scope | Used in | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_BACKEND_API_URL` | Browser + Server | `axios/index.ts`, `apis/user.ts` | Base URL for all axios clients (e.g. `https://stag-api.gogox.co.kr`) |
| `BACKEND_API_URL` | Server-only | `get-html-term-content.ts` | Server-side `fetch()` in `getStaticProps` |
| `NEXT_PUBLIC_ACCESS_TOKEN` | Browser | `interceptors/auth.ts` | Dev: hardcoded bearer token override |
| `NEXT_PUBLIC_ANONYMOUS_ACCESS_TOKEN` | Browser | `interceptors/auth.ts` | Token for guest/anonymous users |
| `NEXT_PUBLIC_APP_ENV` | Browser | `constants/configs.ts` | `"local"` / `"staging"` / `"production"` |
| `NEXT_PUBLIC_BASE_PATH` | Browser | `helpers/link.ts` | Next.js basePath (`/cw`) |
| `NEXT_PUBLIC_KAKAO_CLIENT_ID` | Browser | `components/map/kakao` | Kakao Maps SDK |
| `NEXT_PUBLIC_KAKAO_LOGIN_URL` | Browser | OAuth flow | Kakao OAuth URL |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Browser | OAuth flow | Google OAuth client ID |
| `NEXT_PUBLIC_NAVER_CLIENT_ID` | Browser | OAuth flow | Naver OAuth client ID |
| `NEXT_PUBLIC_FIREBASE_*` (×7) | Browser | `src/lib/firebase/index.ts` | Firebase config |
| `NEXT_PUBLIC_GTM_ID` | Browser | `src/pages/_app.tsx` | Google Tag Manager |
| `NEXT_PUBLIC_WEB1_URL` | Browser | `helpers/landing.ts` | Link to main gogox.com |
| `NEXT_PUBLIC_LANDING_PAGE_URL` | Browser | `helpers/landing.ts` | Redirect after logout |
| `NEXT_PUBLIC_DISABLED_PAGES` | Browser | `constants/configs.ts` | Semicolon-separated disabled page paths |
| `MAINTENANCE_MODE` | Server | `next.config.js` | Enables maintenance mode redirect |

---

## 9. API Call Patterns — Scanner Reference

The following patterns represent every mechanism by which this codebase makes backend API calls.

### Primary Patterns (must detect)

```
# Named axios client calls — defined inside src/lib/apis/*.ts
orderServiceApiClient.get(...)
orderServiceApiClient.post(...)
userServiceApiClient.get(...)
userServiceApiClient.post(...)
userServiceApiClient.put(...)
userServiceApiClient.patch(...)
commonServiceApiClient.get(...)
commonServiceApiClient.delete(...)
notifyServiceApiClient.post(...)
notificationServiceApiClient.post(...)
driverServiceApiClient.*
driverDAServiceApiClient.*
axiosClient.get(...)
axiosClient.post(...)
```

### Service Object Calls (how pages and containers consume APIs)

```
# These are the call sites — trace these back to the named clients above
OrderAPIs.estimate(...)
OrderAPIs.createOrder(...)
OrderAPIs.getOrders(...)
OrderAPIs.getOrder(...)
OrderAPIs.cancelOrder(...)
OrderAPIs.coupons(...)
OrderAPIs.paymentStatus(...)
OrderAPIs.getRoute(...)
OrderAPIs.registerCoupon(...)
OrderAPIs.*

UserAPIs.login(...)
UserAPIs.signup(...)
UserAPIs.profile()
UserAPIs.logout()
UserAPIs.featureFlags()
UserAPIs.*

CommonAPIs.vehicles(...)
CommonAPIs.addressSearch(...)
CommonAPIs.*

NotifyAPIs.sendSms(...)
NotifyAPIs.verifyOtp(...)
NotifyAPIs.*

NotificationAPIs.saveCustomerToken(...)
DriverAPIs.*
```

### SWR Wrapper Patterns (data fetching triggers)

```
useSWR(key, () => *APIs.*(...))
useSWRInfinite(keyFn, (args) => *APIs.*(...))
useSWRImmutable(key, () => *APIs.*(...))
```

### Redux Thunk Patterns (mutation triggers)

```
createAppAsyncThunk("...", async (...) => *APIs.*(...))
createAsyncThunk("...", async (...) => *APIs.*(...))
dispatch(login(...))
dispatch(createOrder(...))
dispatch(getProfile())
```

### Direct Imperative Calls (useEffect / event handlers)

```
*APIs.*(...).then(...).catch(...)   # promise chain in useEffect
await *APIs.*(...)                  # async/await in handlers
```

### Server-side `fetch()` (not axios — runs in getStaticProps)

```
fetch(`${process.env.BACKEND_API_URL}/...`)
```

### Exported URL Constants (not axios calls, but backend endpoints)

```
KCB_START_URL       # browser redirect to identity verification start
PROFILE_API_URL     # "/users/me" — used by auth interceptor
```

---

## Complete Backend Endpoint Inventory

### `/order/api/v1` — Order Service

```
POST   /guest/estimate
POST   /guest/home-moving/estimate
POST   /orders
POST   /home-moving/orders
GET    /orders
GET    /orders/shipping-records
POST   /orders/:id/b2c-cancel
GET    /orders/:id
POST   /orders/:orderId/images
POST   /orders/:id/submit-tip
GET    /orders/statistics
POST   /file/presigned
GET    /guest/orders/:organizationId/:orderId
GET    /guest/mobis/orders/:orderId
GET    /coupons
GET    /orders/:orderId/status
GET    /orders/:orderId/route
GET    guest/orders/route/:orderId
GET    /orders/:orderId/reorder
POST   /coupons/register-user
GET    /guest/etax/hash-order/:orderId
GET    /guest/etax/get-order/:orderId
GET    /guest/etax/verify_biz_registration_number/:bizNumber
POST   /guest/etax/issue_tax_invoice
```

### `/user/api/v1` — User Service

```
POST   /auth/signup
POST   /auth/signup-third-party
POST   /auth/login
POST   /auth/login-by-kakao
POST   /auth/login-by-google
POST   /auth/login-by-naver
POST   /auth/reset-password
GET    /users/me
PUT    /users
POST   /auth/logout
POST   /auth/forgot-password
PATCH  /users/change-password
POST   /users/agreement
POST   /verify-password
GET    /withdraw-reasons
POST   /withdraw
GET    /auth/kcb/authentication-result
GET    /auth/kcb/authentication-start  (browser redirect, not axios)
GET    /feature/flag
GET    /auth/b2c/org-code/validate
POST   /guest/etax/driver-info
GET    /guest/tos-contents             (server-side fetch only)
```

### `/common/api/v1` — Common Service

```
GET    /vehicles
GET    /vehicles/:vehiclePoolId/goods/0
GET    guest/home-moving/goods
GET    /addresses/search
GET    /addresses/search-details
GET    /vehicles/services
GET    /addresses
DELETE /addresses/:addressId
```

### `/notification/api/v1` — Notification / Notify Services

```
POST   /guest/otp/send-sms
POST   /guest/otp/send-email
POST   /guest/otp/verify
POST   /firebase/customer/token
```
