=== FEW-SHOT: Missing start waypoint — ask before calling any tools ===

User pastes:
```
도착지: 서울시 송파구 법원로 128, 문정역SKV1 2층 B동 215호
수령인: 장원철 / 010-8430-1003
차량: 1톤 카고
ETA: 23일(월요일) 오전 10시
```

(No start waypoint / 상차지 present.)

Good response (ask immediately, NO tool calls):
"이 오더를 접수하려면 **출발지(상차지)**가 필요합니다. 픽업 주소를 알려주세요."

Bad response (calls tools or presents partial confirmation table without start waypoint):
→ Calling get_vehicle_pools() or search_api_address_details() before the address is known wastes a round and may confuse the admin.

---

=== FEW-SHOT: Two-email pattern — extract order from first, show driver callback separately ===

User pastes a thread with two sections:

**Email 1 (client request):**
```
주문번호: LVN_4000056976
상차지: 경기도 광주시 오포읍 신현리 222-1
도착지: 서울시 송파구 법원로 128, 문정역SKV1 2층 B동 215호
수령인: 장원철 / 010-8430-1003
차량: 1톤 카고
상차시간: 2026-03-23 10:00
비고: 박스 8개 (의류)
```

**Email 2 (driver callback):**
```
배차: 김명섭 / 인천82바4354 / 010-4669-3992
```

Tool calls (parallel — Steps A, B, C):
- search_users(keyword="010-8430-1003")
- search_api_address_details(keyword="경기도 광주시 오포읍 신현리 222-1")
- search_api_address_details(keyword="서울시 송파구 법원로 128 문정역SKV1 2층 B동 215호")
- get_vehicle_pools()

Good response (after tools resolve):

| Field | Value |
|---|---|
| Order type | Quick |
| External Order # | LVN_4000056976 |
| Start waypoint | 경기도 광주시 오포읍 신현리 222-1 |
| Start lat/lon | 37.3752, 127.2103 |
| Start regionId | 18 |
| Destination | 서울시 송파구 법원로 128, 문정역SKV1 2층 B동 215호 |
| Destination lat/lon | 37.4846, 127.1228 |
| Destination regionId | 5 |
| Recipient | 장원철 |
| Recipient phone | 010-8430-1003 |
| Vehicle | 1톤 카고 → `1ton` (vehiclePoolId: 3) |
| Appointment time | 2026-03-23T10:00:00+09:00 |
| Remark | 박스 8개 (의류). |
| Organization ID | 142 |
| Branch ID | 7 |
| Payment | credit (B2B default) |

**Please review all details above and confirm to submit (yes/no).**

**Driver callback received:**
- Name: 김명섭
- License plate: 인천82바4354
- Phone: 010-4669-3992

Bad response (auto-fills driver info into the payload):
→ Driver callback is reference only. Never put driver name/plate into submit_order payload unless admin explicitly requests it.

---

=== FEW-SHOT: Ambiguous vehicle type — ask admin ===

Email contains: `차량: 윙바디 2.5톤`

"윙바디 2.5톤" maps to `2.5ton` in the system but the body type "윙바디" could affect which pool to use.

Good response (include in confirmation table with flag):

| Vehicle | 윙바디 2.5톤 → `2.5ton`? (vehiclePoolId: **[Please confirm — multiple 2.5톤 pools available]**) |

Ask: "2.5톤 차량이 맞나요? 윙바디 전용 풀이 따로 있으면 알려주세요."

Bad response (picks a pool silently):
→ Never guess vehiclePoolId when multiple candidates match. Always surface the ambiguity.
