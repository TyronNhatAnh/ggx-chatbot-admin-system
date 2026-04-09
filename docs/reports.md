# Report Admin APIs — Structured Response (AI-Readable)

These 4 endpoints mirror the existing report endpoints but return **typed, named struct fields** (`DetailData`) instead of the flat `[][]interface{}` matrix. Intended for AI agents and admin tooling that need to process individual field values.

Base URL: `https://<host>/api/v1`  
Auth: Bearer token (JWT) required — same as all `/api/v1/*` routes.

---

## Common Response Envelope

All 4 endpoints use `PagingSuccessResponse`:

```json
{
  "success": true,
  "data": [ /* array of typed objects */ ],
  "errors": [],
  "meta": {
    "totalCount": 120,
    "isLastPage": false,
    "numPage": 12,
    "additionalData": { /* endpoint-specific totals */ }
  }
}
```

On empty result:
```json
{
  "success": true,
  "data": null,
  "errors": [],
  "meta": { "isLastPage": true }
}
```

On error:
```json
{
  "success": false,
  "errors": [{ "message": "error detail", "field": "", "code": "REQUEST_INVALID" }]
}
```

---

## 1. Customer Statement-of-Use — Summary

**`GET /api/v1/admin/report/statement-of-use/summary`**

Returns one row per organization/business-line combination with aggregated order counts and fares.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fromDate` | string | ✅ | Start date, format `YYYY-MM-DD` |
| `toDate` | string | ✅ | End date, format `YYYY-MM-DD` |
| `pay` | []string | ✅ | Payment method names. Values: `Credit`, `Cash`. Repeat param for multiple: `pay=Credit&pay=Cash` |
| `orgId` | int | — | Filter by organization ID |
| `businesslineCd` | int | — | Filter by business line code |
| `branch` | []string | — | Filter by branch codes |

### Example Request

```
GET /api/v1/admin/report/statement-of-use/summary?fromDate=2025-01-01&toDate=2025-01-31&pay=Credit&orgId=4347&businesslineCd=3
```

### Response `data[]` — `StatementOfUseDataSummary`

| Field | Type | Description |
|---|---|---|
| `organizationId` | int | Organization (기업) ID |
| `organizationCode` | string | Organization code |
| `organizationName` | string | Organization name |
| `orderCount` | int | Total number of orders in period |
| `customerFare` | float64 | Total customer fare (고객운임) |
| `bonus` | float64 | Total bonus amount (고객 보너스) |

### Response `meta.additionalData` — `SummaryAdditionalData`

| Field | Type | Description |
|---|---|---|
| `header` | []string | Column labels (Korean) |
| `totalCustomerFare` | string | Sum of all `customerFare` values, formatted |
| `totalOrderCount` | int | Sum of all `orderCount` values |

### Example Response

```json
{
  "success": true,
  "data": [
    {
      "organizationId": 4347,
      "organizationCode": "ORG001",
      "organizationName": "테스트기업",
      "orderCount": 152,
      "customerFare": 3820000.0,
      "bonus": 50000.0
    }
  ],
  "errors": [],
  "meta": {
    "totalCount": 1,
    "isLastPage": true,
    "numPage": 1,
    "additionalData": {
      "header": ["기업ID","기업코드","기업명","거래유형","주문","고객운임","고객 보너스"],
      "totalCustomerFare": "3,820,000",
      "totalOrderCount": 152
    }
  }
}
```

---

## 2. Customer Statement-of-Use — Detail

**`GET /api/v1/admin/report/statement-of-use/detail`**

Returns one row per individual order with full order, address, fare breakdown, and driver info.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fromDate` | string | ✅ | Start date, format `YYYY-MM-DD` |
| `toDate` | string | ✅ | End date, format `YYYY-MM-DD` |
| `pay` | []string | ✅ | Payment method names. Values: `Credit`, `Cash` |
| `orgId` | int | — | Filter by organization ID |
| `businesslineCd` | int | — | Filter by business line code |
| `pageSize` | int | — | Page size (default: `10`) |
| `pageIndex` | int | — | Page number, 1-based (default: `1`) |

### Example Request

```
GET /api/v1/admin/report/statement-of-use/detail?fromDate=2025-01-01&toDate=2025-01-31&pay=Credit&orgId=4347&pageSize=20&pageIndex=1
```

### Response `data[]` — `StatementOfUseDataDetail`

| Field | Type | Description |
|---|---|---|
| `orderRequestId` | int64 | Order ID |
| `orderRequestCreatedDate` | string | Order creation datetime (KST) |
| `orderRequestAtpointmentDate` | string (ISO8601) | Requested pickup/appointment datetime |
| `orderRequestCompleteDate` | string | Order completion datetime |
| `requestVehicleType` | string | Requested vehicle type |
| `deliveryVehicleType` | string | Actual delivery vehicle type |
| `orderStatus` | string | Order status label (Korean) |
| `statusCd` | uint | Order status code |
| `organizationName` | string | Organization name |
| `organizationCode` | string | Organization code |
| `branchName` | string | Branch name |
| `branchCode` | string | Branch code |
| `businessLineName` | string | Business line name |
| `orderOwnerName` | string | Order owner name |
| `orderOwnerContactNo` | string | Order owner phone |
| `senderName` | string\|null | Sender name |
| `startAddress` | string | Pickup address |
| `receiverName` | string | Receiver name |
| `receiverContactNo` | string | Receiver phone |
| `endAddress` | string | Drop-off address |
| `goods` | string | Goods description |
| `basePrice` | float64\|null | Base fare |
| `chargingPrice` | string\|null | Surcharge |
| `extraPrice` | float64\|null | Extra charge |
| `bonus` | float64\|null | Bonus amount |
| `returnPrice` | float64\|null | Return trip fee |
| `cancellationFee` | float64\|null | Cancellation fee |
| `roundDownPrice` | string\|null | Round-down adjustment |
| `totalPrice` | float64 | Total fare charged to customer |
| `vatPrice` | float64\|null | VAT amount |
| `consignmentPrice` | float64\|null | Consignment (탁송) price |
| `paymentMethod` | string | Payment method label |
| `driverName` | string | Assigned driver name |
| `driverUserTypeTitle` | string | Driver type label |
| `externalDriverName` | string\|null | External driver name (if applicable) |
| `externalDriverPhoneNumber` | string\|null | External driver phone |
| `notes` | string | Order notes |
| `remark` | string | Admin remark |
| `externalOrderId` | string | External order reference ID |
| `pickupAt` | string\|null | Actual pickup timestamp |
| `nationalWideDelivery` | string | Nationwide delivery flag/type |
| `vehiclePoolId` | int | Vehicle pool ID |

### Response `meta.additionalData` — `DetailAdditionalData`

| Field | Type | Description |
|---|---|---|
| `header` | []interface{} | Column labels for display |
| `totalCount` | int64 | Total matching rows (for pagination) |

### Example Response

```json
{
  "success": true,
  "data": [
    {
      "orderRequestId": 100023456,
      "orderRequestCreatedDate": "2025-01-05 09:12:33",
      "orderRequestAtpointmentDate": "2025-01-05T10:00:00+09:00",
      "orderRequestCompleteDate": "2025-01-05 11:45:00",
      "requestVehicleType": "1톤",
      "deliveryVehicleType": "1톤",
      "orderStatus": "배송 완료",
      "statusCd": 4,
      "organizationName": "테스트기업",
      "organizationCode": "ORG001",
      "branchName": "서울지점",
      "branchCode": "BR001",
      "businessLineName": "일반화물",
      "orderOwnerName": "홍길동",
      "orderOwnerContactNo": "010-1234-5678",
      "senderName": { "String": "홍길동", "Valid": true },
      "startAddress": "서울시 강남구 테헤란로 123",
      "receiverName": "김철수",
      "receiverContactNo": "010-9876-5432",
      "endAddress": "서울시 마포구 월드컵로 456",
      "goods": "서류",
      "basePrice": { "Float64": 25000, "Valid": true },
      "chargingPrice": { "String": "0", "Valid": true },
      "extraPrice": { "Float64": 0, "Valid": true },
      "bonus": { "Float64": 0, "Valid": false },
      "returnPrice": { "Float64": 0, "Valid": false },
      "cancellationFee": { "Float64": 0, "Valid": false },
      "roundDownPrice": { "String": "0", "Valid": true },
      "totalPrice": 27500.0,
      "vatPrice": { "Float64": 2500, "Valid": true },
      "consignmentPrice": { "Float64": 0, "Valid": false },
      "paymentMethod": "후불",
      "driverName": "이기사",
      "driverUserTypeTitle": "정기사",
      "externalDriverName": { "String": "", "Valid": false },
      "externalDriverPhoneNumber": { "String": "", "Valid": false },
      "notes": "",
      "remark": "",
      "externalOrderId": "",
      "pickupAt": { "Time": "2025-01-05T10:05:00Z", "Valid": true },
      "nationalWideDelivery": "N",
      "vehiclePoolId": 3
    }
  ],
  "errors": [],
  "meta": {
    "totalCount": 152,
    "isLastPage": false,
    "numPage": 8,
    "additionalData": {
      "header": ["주문번호", "주문생성일시", "..."],
      "totalCount": 152
    }
  }
}
```

> **Note on nullable fields:** Fields typed `null.Float`, `null.String`, `null.Time` serialize as `{ "Float64": <value>, "Valid": <bool> }`, `{ "String": <value>, "Valid": <bool> }`, etc. When `Valid` is `false`, the value should be treated as null/absent.

---

## 3. Driver Statement-of-Use — Summary

**`GET /api/v1/admin/report/statement-of-use-driver/summary`**

Returns one row per driver with aggregated financial settlement data for the period.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fromDate` | string | ✅ | Start date, format `YYYY-MM-DD` |
| `toDate` | string | ✅ | End date, format `YYYY-MM-DD` |
| `driverType` | string | ✅ | Must be `normalDriver` (currently only supported value) |
| `orgId` | int | — | Filter by organization ID |
| `driverId` | int64 | — | Filter by specific driver user ID |
| `driverOrg` | int64 | — | Filter by driver's organization ID |
| `taxPlayerCd` | []int | — | Filter by tax player type code. Repeat for multiple: `taxPlayerCd=1&taxPlayerCd=2` |
| `eTaxStatus` | []string | — | Filter by e-tax status. Repeat for multiple |
| `isRevised` | bool | — | Filter revised records only |

### Example Request

```
GET /api/v1/admin/report/statement-of-use-driver/summary?fromDate=2025-01-01&toDate=2025-01-31&driverType=normalDriver&orgId=17
```

### Response `data[]` — `DriverDataSummary`

| Field | Type | Description |
|---|---|---|
| `driverUserId` | int64 | Driver's user ID |
| `driverName` | string | Driver name |
| `driverOrganizationName` | string | Driver's affiliated organization name |
| `bizRegistrationNumber` | string | Business registration number (사업자번호) |
| `taxPlayerCd` | int | Tax player type code |
| `taxPlayerName` | string | Tax player type label |
| `payCd` | int | Payment type code |
| `businessPayName` | string | Payment type label |
| `residentRegistrationNumber` | string | Driver SSN — **masked in API response, full value in Excel export only** |
| `phoneNumber` | string | Driver phone |
| `deliveryVehicle` | string | Vehicle type |
| `costRatio` | string | Cost ratio / expense ratio (경비율) |
| `bankNumber` | string | Bank code |
| `bankName` | string | Bank name |
| `bankAccountName` | string | Account holder name |
| `bankAccountNumber` | string | Account number |
| `finalPrice` | float64 | Final fare amount (최종운임) |
| `bonus` | float64 | Bonus |
| `incentive` | float64 | Incentive |
| `couponPrice` | float64 | Coupon discount amount |
| `returnPrice` | float64 | Return trip fee |
| `commissionBaseAmount` | float64 | Commission base amount (커미션 대상금액) |
| `commissionPrice` | float64 | Commission fee (커미션) |
| `totalPrice` | float64 | Total (기사운임) |
| `driverIncome` | float64 | (신고) Driver income (기사소득액) |
| `driverVAT` | float64 | (신고) Driver VAT (부가세) |
| `driverIncomeTax` | float64 | (신고) Income tax (소득세) |
| `industry` | float64 | (신고) Industrial accident insurance (산재보험료) |
| `engage` | float64 | (신고) Employment insurance (고용보험료) |
| `rawEngage` | float64 | Raw engagement insurance value |
| `consignmentPrice` | float64 | Consignment fee (탁송료) |
| `payToDriver` | float64 | (신고) Net pay to driver (지급액) |

### Response `meta.additionalData` — `SummaryAdditionalDriverData`

| Field | Type | Description |
|---|---|---|
| `header` | []interface{} | Column labels (Korean) |
| `totalDriverCount` | int | Total number of distinct drivers |

### Example Response

```json
{
  "success": true,
  "data": [
    {
      "driverUserId": 9921,
      "driverName": "이기사",
      "driverOrganizationName": "고고밴코리아",
      "bizRegistrationNumber": "123-45-67890",
      "taxPlayerCd": 1,
      "taxPlayerName": "일반과세자",
      "payCd": 2,
      "businessPayName": "후불",
      "residentRegistrationNumber": "******-*******",
      "phoneNumber": "010-****-5678",
      "deliveryVehicle": "1톤",
      "costRatio": "0.243",
      "bankNumber": "004",
      "bankName": "국민은행",
      "bankAccountName": "이기사",
      "bankAccountNumber": "123456789012",
      "finalPrice": 850000.0,
      "bonus": 10000.0,
      "incentive": 0.0,
      "couponPrice": 0.0,
      "returnPrice": 0.0,
      "commissionBaseAmount": 860000.0,
      "commissionPrice": 77400.0,
      "totalPrice": 782600.0,
      "driverIncome": 782600.0,
      "driverVAT": 78260.0,
      "driverIncomeTax": 24542.0,
      "industry": 5478.0,
      "engage": 6261.0,
      "rawEngage": 6261.0,
      "consignmentPrice": 0.0,
      "payToDriver": 668059.0
    }
  ],
  "errors": [],
  "meta": {
    "totalCount": 38,
    "isLastPage": true,
    "numPage": 1,
    "additionalData": {
      "header": ["기사ID","기사명","기사그룹(기업)","사업자번호","..."],
      "totalDriverCount": 38
    }
  }
}
```

---

## 4. Driver Statement-of-Use — Detail

**`GET /api/v1/admin/report/statement-of-use-driver/detail`**

Returns one row per order per driver — the most granular view, combining order info with full driver financial breakdown.

### Query Parameters

Same as Driver Summary, plus pagination:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fromDate` | string | ✅ | Start date, format `YYYY-MM-DD` |
| `toDate` | string | ✅ | End date, format `YYYY-MM-DD` |
| `driverType` | string | ✅ | Must be `normalDriver` |
| `orgId` | int | — | Filter by organization ID |
| `driverId` | int64 | — | Filter by specific driver user ID |
| `driverOrg` | int64 | — | Filter by driver's organization ID |
| `taxPlayerCd` | []int | — | Filter by tax player type code |
| `eTaxStatus` | []string | — | Filter by e-tax status |
| `isRevised` | bool | — | Revised records only |
| `pageSize` | int | — | Page size (default: `10`) |
| `pageIndex` | int | — | Page number, 1-based (default: `1`) |

### Example Request

```
GET /api/v1/admin/report/statement-of-use-driver/detail?fromDate=2025-01-01&toDate=2025-01-31&driverType=normalDriver&orgId=17&pageSize=50&pageIndex=1
```

### Response `data[]` — `DriverDataDetail`

Superset of Driver Summary fields plus order-level fields:

**Order Info**

| Field | Type | Description |
|---|---|---|
| `orderRequestId` | string | Order ID |
| `organizationName` | string | Organization name |
| `organizationCode` | string | Organization code |
| `branchName` | string | Branch name |
| `branchCode` | string | Branch code |
| `businessLineName` | string | Business line |
| `orderOwnerName` | string | Order owner name |
| `orderOwnerContactNo` | string | Order owner phone |
| `senderName` | string\|null | Sender name |
| `startAddress` | string | Pickup address |
| `receiverName` | string | Receiver name |
| `receiverContactNo` | string | Receiver phone |
| `endAddress` | string | Drop-off address |
| `notes` | string | Order notes |
| `parentId` | int64 | Parent order ID (0 if none) |
| `orderRequestCreatedDate` | string | Order creation datetime |
| `orderRequestAtpointmentDate` | string | Appointment datetime |
| `orderRequestCompleteDate` | string | Completion datetime |
| `requestVehicleType` | string | Requested vehicle type |
| `commissionRatioVehicle` | string | Commission ratio from vehicle type |
| `commissionRatioDriver` | string | Driver commission discount ratio |
| `appliedCommissionRatio` | string | Effective commission ratio |
| `orderStatus` | string | Order status label |
| `nationalWideDelivery` | string | Nationwide delivery flag |

**Driver Info** (same fields as Summary)

| Field | Type | Description |
|---|---|---|
| `driverUserId` | int64 | Driver user ID |
| `driverName` | string | Driver name |
| `driverOrganizationName` | string | Driver's organization |
| `bizRegistrationNumber` | string | Business registration number |
| `residentRegistrationNumber` | string | SSN — **masked in API** |
| `phoneNumber` | string | Phone — **masked in API** |
| `taxPlayerCd` | int | Tax player code |
| `taxPlayerName` | string | Tax player label |
| `deliveryVehicle` | string | Vehicle type |
| `costRatio` | string | Expense ratio |
| `bankNumber` | string | Bank code |
| `bankName` | string | Bank name |
| `bankAccountName` | string | Account holder |
| `bankAccountNumber` | string | Account number |

**Financial Fields** (per-order breakdown)

| Field | Type | Description |
|---|---|---|
| `finalPrice` | float64 | Final fare |
| `bonus` | float64 | Bonus |
| `CustomerFare` | float64 | Incentive (note: json key is `CustomerFare`) |
| `couponPrice` | float64 | Coupon |
| `returnPrice` | float64 | Return fee |
| `payCd` | string | Payment type code |
| `paymentMethod` | string | Payment method label |
| `commissionBaseAmount` | float64 | Commission base |
| `commissionExemption` | string | Commission exemption flag |
| `commissionPrice` | float64 | Commission |
| `totalPrice` | float64 | Driver fare total |
| `driverIncome` | float64 | (신고) Driver income |
| `driverVAT` | float64 | (신고) VAT |
| `driverIncomeTax` | float64 | (신고) Income tax |
| `consignmentPrice` | float64 | Consignment fee |
| `industry` | float64 | (신고) Industrial accident insurance |
| `engage` | float64 | (신고) Employment insurance |
| `payToDriver` | float64 | (신고) Net pay to driver |

**E-Tax Fields**

| Field | Type | Description |
|---|---|---|
| `mgtNum` | string\|null | Tax invoice management number |
| `etaxStatus` | string\|null | E-tax issue status label |
| `ntsSendKey` | string\|null | NTS send key (국세청 등록번호) |
| `writedate` | string\|null | Tax invoice issue date (작성일자) |

### Response `meta.additionalData` — `DetailAdditionalData`

| Field | Type | Description |
|---|---|---|
| `header` | []interface{} | Column labels (Korean) — same as `DriverDetailDisplayHeader` |
| `totalCount` | int64 | Total matching rows |

### Example Response

```json
{
  "success": true,
  "data": [
    {
      "orderRequestId": "100023456",
      "organizationName": "테스트기업",
      "organizationCode": "ORG001",
      "branchName": "서울지점",
      "branchCode": "BR001",
      "businessLineName": "일반화물",
      "orderOwnerName": "홍길동",
      "orderOwnerContactNo": "010-1234-5678",
      "senderName": { "String": "홍길동", "Valid": true },
      "startAddress": "서울시 강남구 테헤란로 123",
      "receiverName": "김철수",
      "receiverContactNo": "010-****-5432",
      "endAddress": "서울시 마포구 월드컵로 456",
      "notes": "",
      "parentId": 0,
      "orderRequestCreatedDate": "2025-01-05 09:12:33",
      "orderRequestAtpointmentDate": "2025-01-05 10:00:00",
      "orderRequestCompleteDate": "2025-01-05 11:45:00",
      "requestVehicleType": "1톤",
      "commissionRatioVehicle": "9",
      "commissionRatioDriver": "0",
      "appliedCommissionRatio": "9",
      "orderStatus": "배송 완료",
      "nationalWideDelivery": "N",
      "driverUserId": 9921,
      "driverName": "이기사",
      "driverOrganizationName": "고고밴코리아",
      "bizRegistrationNumber": "123-45-67890",
      "residentRegistrationNumber": "******-*******",
      "phoneNumber": "010-****-5678",
      "taxPlayerCd": 1,
      "taxPlayerName": "일반과세자",
      "deliveryVehicle": "1톤",
      "costRatio": "0.243",
      "bankNumber": "004",
      "bankName": "국민은행",
      "bankAccountName": "이기사",
      "bankAccountNumber": "123456789012",
      "finalPrice": 28000.0,
      "bonus": 0.0,
      "CustomerFare": 0.0,
      "couponPrice": 0.0,
      "returnPrice": 0.0,
      "payCd": "2",
      "paymentMethod": "후불",
      "commissionBaseAmount": 28000.0,
      "commissionExemption": "N",
      "commissionPrice": 2520.0,
      "totalPrice": 25480.0,
      "driverIncome": 25480.0,
      "driverVAT": 2548.0,
      "driverIncomeTax": 799.0,
      "consignmentPrice": 0.0,
      "industry": 178.0,
      "engage": 204.0,
      "payToDriver": 21751.0,
      "mgtNum": { "String": "20250105-001", "Valid": true },
      "etaxStatus": { "String": "발급완료", "Valid": true },
      "ntsSendKey": { "String": "NTSKEY123", "Valid": true },
      "writedate": { "String": "2025-01-10", "Valid": true }
    }
  ],
  "errors": [],
  "meta": {
    "totalCount": 890,
    "isLastPage": false,
    "numPage": 18,
    "additionalData": {
      "header": ["주문번호","기업명","기업코드","..."],
      "totalCount": 890
    }
  }
}
```

---

## Notes for AI Tool Implementation

1. **Date range**: Both `fromDate` and `toDate` are always required. Use `YYYY-MM-DD` format.
2. **`pay` / `driverType` are required**: Summary endpoints for customers need `pay`, driver endpoints need `driverType=normalDriver`.
3. **Pagination**: Use `pageSize` + `pageIndex` for detail endpoints. Summary endpoints return all rows without pagination (`pageSize`/`pageIndex` are ignored; `meta.totalCount` equals `data.length`).
4. **Nullable fields**: `null.String`, `null.Float`, `null.Time` fields serialize as objects `{ "String": "...", "Valid": true }`. Always check `Valid` before reading the value.
5. **`CustomerFare` JSON key on DriverDataDetail**: The incentive field has the JSON key `"CustomerFare"` (capital C) — this is a known naming inconsistency in the codebase.
6. **PII masking**: `residentRegistrationNumber` and `phoneNumber` in driver endpoints are masked in API responses. Full values are only present in Excel downloads.
7. **`pay` values**: Valid values are `Credit` (후불/credit account) and `Cash` (현금). The API internally maps these to numeric `payCD` codes (`Credit=2`).
