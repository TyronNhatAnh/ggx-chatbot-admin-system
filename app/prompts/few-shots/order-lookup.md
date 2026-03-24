=== FEW-SHOT: Order price detail ===

User: "chi tiết giá đơn 1348042"

Tool call: get_orders_admin_panel(order_request_id=1348042)
Tool result (abbreviated):
{
  "orders": [{
    "orderId": 1348042,
    "price": 29000,
    "calculationPrice": {"baseFee": 25000, "vatAmount": 2500, "express": 0, "couponDiscount": 0, "total": 29000, "preVatFee": 26500, "consignment": 1500},
    "driverFee": 29000,
    "payMethod": "credit"
  }]
}

Good response:
"Đây là chi tiết giá cho đơn hàng 1348042:

| Mục | Số tiền |
|---|---|
| Phí cơ bản (Base Fee) | 25,000 |
| Phí ủy thác (Consignment) | 1,500 |
| Phí trước VAT | 26,500 |
| VAT | 2,500 |
| **Tổng** | **29,000** |

- Phí tài xế: 29,000
- Phương thức thanh toán: credit"

Bad response (too terse — missing breakdown):
"Đây là chi tiết giá cho đơn hàng 1348042:
Giá khách hàng: 29000
Giá tài xế: 29000"
