# 📋 Order Service API Audit — Chi Tiết

## 🎯 Mục tiêu
Audit APIs trong order-service theo Web2 flow để:
1. Xác định APIs thực sự được sử dụng (không chỉ GET/POST bừa bãi)
2. Phân tích ý nghĩa của từng API
3. Thêm các tools hữu ích vào orchestrator

## 🔍 Kết quả: 3 Tools Mới

### ✅ Tool #1: `get_order_route(order_id)` 
**Endpoint**: `GET /orders/{orderId}/route`

**Khi nào dùng:**
- "Tuyến đường giao hàng là gì?" 
- "Điểm dừng tiếp theo ở đâu?"
- "Chi tiết waypoints của đơn hàng này?"
- Theo dõi tiến trình giao hàng real-time

**Dữ liệu trả về:**
- Danh sách waypoints có thứ tự
- Status của từng waypoint (Pending, Completed, Failed)
- Tọa độ GPS, khoảng cách
- Thời gian yêu cầu, thời gian đến

**Khác với `get_order_detail`:**
- `get_order_detail` trả về waypoints như một phần của order
- `get_order_route` chuyên trả về route với dữ liệu live updates

**Ví dụ:**
```
getorder_route("ORD-12345") 
→ waypoints: [
    {arrangement: 1, status: "Completed", address: "Seoul Tower", lat: 37.55, lon: 126.98},
    {arrangement: 2, status: "Failed", address: "Busan Port", lat: 35.09, lon: 129.03}
  ]
```

---

### ✅ Tool #2: `get_order_shipping_records(keyword)` 
**Endpoint**: `GET /orders/shipping-records?keyword=...`

**Khi nào dùng:**
- "Những địa chỉ nào mình đã giao hàng?"
- "Gợi ý địa chỉ gần đây để tạo đơn mới"
- Customer muốn xem lịch sử đích đến

**Dữ liệu trả về:**
- Danh sách các waypoint từ **các đơn đã hoàn thành**
- Địa chỉ, tọa độ GPS, tên địa điểm
- Dùng để gợi ý khi user tạo đơn mới

**Use case thực tế:**
Web2 frontend gọi `.getRecentAddresses()` để show dropdown suggestion khi user nhập "To" address.

**Ví dụ:**
```
get_order_shipping_records("Seoul")
→ records: [
    {name: "Seoul Tower", address: "1 Teheran-ro", lat: 37.55, lon: 126.98},
    {name: "Seoul Station", address: "405 Namdaemun-ro", lat: 37.55, lon: 126.97}
  ]
```

---

### ✅ Tool #3: `get_order_reorder_info(order_id)` 
**Endpoint**: `GET /orders/{orderId}/reorder`

**Khi nào dùng:**
- "Tôi muốn đặt lại đơn hàng này"
- "Dữ liệu để reorder là gì?"
- "Hàng hóa trước đây là gì?"

**Dữ liệu trả về:**
- Origin & destination từ order cũ
- Danh sách hàng hóa (goods)
- Thời gian hẹn
- Ghi chú/remarks

**Use case thực tế:**
Khi customer click button "Reorder", Web2 phải fetch dữ liệu để pre-fill form.

**Ví dụ:**
```
get_order_reorder_info("ORD-12345")
→ {
    orderId: "ORD-12345",
    fromPlace: {name: "Home", address: "123 Main St"},
    toPlace: {name: "Office", address: "456 Work Ave"},
    goods: [{name: "Box A", quantity: 2}, {name: "Document", quantity: 1}],
    appointmentAt: "2026-03-18T14:00:00Z"
  }
```

---

## 🚫 APIs Loại Bỏ (& Lí do)

| API | Lí do |
|-----|-------|
| `GET /guest/orders/{orgId}/{orderId}` | Guest-only → không cần cho authenticated admin assistant |
| `GET /guest/mobis/orders/{orderId}` | Niche Mobis B2B integration → quá specific |
| `GET /guest/orders/route/{orderId}` | Guest-only → có `get_order_route` authenticated rồi |
| `GET /orders/{orderId}/admin` | Admin-only detail path → có thể thêm sau nếu cần |
| `GET /order-da/{orderId}` | Too niche (DA context) |
| `GET /order-control/search` | Separate admin operations concern |
| `GET /guest/etax/*` endpoints | E-Tax invoice flow → không phải admin assistant scope |

---

## 🤔 Insights từ Audit

### 1️⃣ POST endpoints không phải luôn là CREATE
Ví dụ:
- `/guest/check-tip` → Đây là **READ** operation (check expected tip, không tạo)
- `/guest/check-price-driver` → Đây là **READ** operation (estimate giá, không tạo)
- `/guest/estimate` → Đây là **READ** operation (tính giá, không tạo)

✅ Đã xử lý đúng: có tools `estimate_guest_price`, `check_driver_price`

### 2️⃣ Guest vs Authenticated API Paths
**Pattern:**
- `/guest/...` endpoints → không cần auth, trả về public data
- Authenticated endpoints → cần Bearer token, trả về user-specific data

**Quyết định:** Admin assistant chỉ cần authenticated paths (không cần guest paths vì admin không phải guest user)

### 3️⃣ Web2 vs Admin Use Cases Khác Nhau
**Web2 (Customer):**
- Tìm order, tính giá, track, reorder, giới hạn coupons

**Admin:**
- Status, hủy, thanh toán, thống kê, báo cáo

✅ Current tool set cover cả 2 perspectives.

### 4️⃣ Payload Optimization Quan Trọng
Theo copilot-instructions.md, target latency: **3-6 seconds/request**

Token efficiency rules:
- Tất cả new tools sử dụng `_slim_*` methods
- Waypoints, goods, prices có compact representation
- No returning raw, unprocessed nested objects

---

## 📁 Files Modified

### 1. `app/services/order_service_client.py`
**Thêm 3 methods:**
```python
def get_order_route(order_id: str) -> dict
def get_order_shipping_records(keyword: str = "") -> dict
def get_order_reorder_info(order_id: str) -> dict
```

**Pattern tuân theo:**
- Try-except với error handling (404, network, other)
- Logging với HTTP status + elapsed time
- Payload unwrapping & slimming
- Consistent return format: `{"error": ..., "detail": ...}` hoặc data dict

### 2. `app/tools/order_tools.py`
**Thêm 3 function wrappers:**
```python
def get_order_route(order_id: str) -> dict
def get_order_shipping_records(keyword: str = "") -> dict
def get_order_reorder_info(order_id: str) -> dict
```

**Docstrings hướng dẫn:**
- Khi nào dùng (use case ngắn)
- Endpoint nào được gọi (GET ...)
- Dữ liệu trả về là gì

### 3. `app/tools/__init__.py`
**Cập nhật:**
- Import 3 tools mới từ `order_tools`
- Thêm vào `ALL_TOOL_FUNCTIONS` list

### 4. `app/orchestrator/prompt_builder.py`
**Cập nhật system prompt:**
- Thêm hướng dẫn khi nào gọi từng tool mới
- Include use cases ("are you asking about...", "what if user says...")
- Clarify khác biệt vs tools tương tự

---

## ✅ Verification

```bash
# 1. Import test
✅ All 3 tools imported successfully

# 2. Registration test
✅ All 3 tools in TOOL_REGISTRY

# 3. Orchestrator startup
✅ AIOrchestrator initialized
✅ System prompt contains new tools
```

---

## 🎯 Next Steps (Optional)

Future enhancements (out of scope cho audit này):
1. `GET /orders/{orderId}/admin` - Admin-specific detail view
2. `GET /order-control/search` - Advanced order filtering
3. Statement-of-use reporting endpoints
4. Admin-side order statistics (vs current per-user stats)

---

## Summary
✅ Audited 30+ order APIs  
✅ Identified 3 high-value GET endpoints used by Web2  
✅ Implemented with consistent error handling & payload optimization  
✅ Updated system prompt with tool guidance  
✅ All tests passing  
✅ No breaking changes to existing tools
