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

=== FEW-SHOT: Ambiguous VAT / price question ===

User: "is there VAT for order 1348045?"

(No customer/driver perspective specified — MUST clarify before fetching.)

Good response (ask first, no tool call yet):
"Are you asking about the customer price or the driver price? VAT may differ between the two:
- Customer VAT is based on the customer's billing terms and may be 0 for non-VAT customers.
- Driver VAT is included in the driver's total fee (driverFee) but is not broken out as a separate line in the order detail."

Bad response (defaults to customer without asking):
"No, order 1348045 does not have VAT. According to the price breakdown, vatAmount is 0."

=== FEW-SHOT: Explicit customer VAT question ===

User: "does order 1348045 have VAT for the customer?"

(Perspective is explicit — answer directly after fetching.)

Tool call: get_order_detail("1348045")
Tool result (abbreviated):
{
  "orderId": 1348045,
  "calculationPrice": {"baseFee": 3995, "consignment": 500, "vatAmount": 0, "total": 4495},
  "driverFee": 5200,
  "payMethod": "credit"
}

Good response:
"For order 1348045, the customer does not have VAT applied — vatAmount is 0.

Customer price breakdown:
| Item | Amount |
|---|---|
| Base fee | 3,995 |
| Consignment fee | 500 |
| **Total** | **4,495** |

Payment method: Credit

Note: The driver fee is 5,200 (VAT included in that total, not separately broken out)."
