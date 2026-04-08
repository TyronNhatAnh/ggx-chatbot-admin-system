# Tool Verification Questions

Test questions to verify all tools are working correctly. Organized into 20 sessions (~5 questions each).
Email dispatch excluded.

---

## ORDER TOOLS

### Session 1 — Order Detail (`get_order_detail`)
1. Show me the full details of order `1348180`
2. What is the current status of order `1348181`? Which driver is assigned?
3. What are the waypoints for order `1348182`?
4. What payment method does order `1348190` use? What is the total amount?
5. What goods are in order `1348180`? Are there any special notes?

### Session 2 — Order List, Filter & Submit (`get_orders_admin_panel`, `submit_order`)
1. List the 5 most recent orders in the system
2. Show me all orders currently Completed (status 3) today
3. List orders assigned to driver ID 360412 this week
4. Are there any recently cancelled orders for org ID 17?
5. Search for orders with keyword "mymy" — by customer or driver name
6. What fields does `submit_order` need to create a Quick order? (describe without placing the order)

### Session 3 — Payment & Cancel Fee (`get_order_payment_status`, `get_order_cancel_fee`)
1. Check the payment status of order `1348180`
2. Has order `1348181` been paid?
3. How much is the cancellation fee for order `1348182` if cancelled now?
4. Calculate the cancel fee for order `1348183`
5. Does order `1348184` have branchPay? What is the payment status?

### Session 4 — Order History (`get_order_history`)
1. Show me the change history for order `1348185`
2. Was the price of order `1348186` ever modified? Who changed it?
3. What statuses has order `1348187` gone through over time?
4. Show the 10 most recent changes for order `1348188`
5. Which user last updated the details of order `1348189`?

### Session 5 — Multi-turn Order Context
1. Find orders assigned to a driver named "TyronTest" — are there any results?
2. *(follow-up)* Show me the full details of the first order in those results
3. *(follow-up)* What is the payment status of that order?
4. *(follow-up)* Is there a cancellation fee if we cancel it now?
5. *(follow-up)* Any change history on that order?

---

## USER TOOLS

### Session 6 — User Lookup (`search_users`)
1. What is the profile of user name "tyron"?
2. Find a user with phone or email `0106083106`
3. Is there a user named "TyronTestCreateAPICW" in the system? What is their ID?
4. Find all users belonging to org ID 17

### Session 7 — Organization (`search_organizations`)
1. Search for an organization named "GoGoX"
2. List all B2B organizations in the system
3. Which organizations have "Logistics" in their name?
4. How many branches does org ID 17 have?

### Session 8 — Branch (`search_branches`)
1. Find a branch with "서울" in the name
2. List all branches under org ID 17
3. Which branches have "서울" in their name?
4. *(follow-up from Q1)* What is the address of that branch?

### Session 9 — Admin Roles & Permissions (`list_admin_roles`, `list_admin_departments`, `list_admin_menus`, `get_admin_permissions`, `get_accessible_menu_tree`)
1. List all admin roles in the system
2. What permissions does role ID 3 have?
3. List all admin departments
4. What does the menu tree look like for role ID 5?
5. List all available admin menus

---

## DRIVER TOOLS

### Session 10 — Driver Profile & Search (`get_driver`, `search_drivers`)
1. What is the profile of driver ID 225324?
2. Find a driver with name or phone "0106083106"
3. What is the orderCap and creditAmount of driver "tyron.driver1"?
4. Search for drivers named "tyron" — how many results come back?
5. What level and vehicle type does driver ID 225324 have?

### Session 11 — Vehicle Pools (`get_vehicle_pools`)
1. What vehicle pools are available in the system?
2. What are the vehicle pool IDs and their names?
3. Which pool does a small truck belong to?
4. *(follow-up)* What is the ID of that pool?
5. List all vehicle pools and briefly describe each one

### Session 12 — Driver Fare (`calculate_driver_fare`)
1. Calculate the fare for driver ID 225324 on order ID 123456
2. How much will driver ID 225324 earn from order 654321?
3. What does the fare breakdown look like for driver 225324 on order 111111?
4. How much VAT is included in the fare for driver 225324 on order 123456?
5. *(multi-step)* Find a driver named "Tran Van B", then calculate their fare on order 999

---

## COMMON TOOLS

### Session 13 — Vehicle Prices (`get_vehicle_prices`)
1. What are the vehicle prices for order type "Quick"?
2. Show me the price list for order type "Delivery"
3. What vehicle types and prices are available for "HomeMoving"?
4. Compare vehicle prices between Quick and Delivery order types
5. What vehicle tiers are available for a Quick order?

### Session 14 — Address Search (`get_addresses`, `search_api_addresses`, `search_api_address_details`)
1. Search for the address "서울 종로구 새문안로" in the system
2. Search external addresses with keyword "서울 종로구 새문안로"
3. Find saved addresses for user ID 10001 with keyword "서울 종로구 새문안로"
4. Get detailed address results for "서울 종로구 새문안로"
5. What addresses match the keyword "서울 종로구 새문안로"?

---

## KNOWLEDGE / DOCS TOOLS

### Session 15 — Enum & Status Code (`lookup_enum`, `explain_status`)
1. What does statusCd=3 mean?
2. Look up the "OrderStatus" enum — what values does it have?
3. What payment method is PayCd=2?
4. What does statusCd=7 mean, and which entity does it apply to?
5. What vehicle types are defined in the "VehicleType" enum?

### Session 16 — Endpoint Search & Handler Context (`search_endpoints`, `get_handler_context`, `list_available_docs`)
1. Which API handles fetching order details?
2. Which handler is responsible for cancelling an order?
3. What handler processes the `/admin/orders` endpoint?
4. What does the `GetOrderDetail` handler do? Which services does it call?
5. What steps does the `CancelOrderB2C` handler perform?

### Session 17 — Code Search (`search_codebase`)
1. Search the codebase for the `B2COrderDetail` struct definition and its fields
2. Search the codebase: what does the `Order` struct look like in the backend?
3. Search the codebase: "how is pricing calculated?"
4. Search the codebase: which struct contains the `appointmentAt` field?
5. Search for: "order cancellation validation logic"

### Session 18 — Graph Traversal & Flow Tracing (`find_api_consumers`, `traverse_graph`, `get_knowledge_stats`)
1. Which services does the `GetOrderDetail` handler call? Traverse the graph to find out
2. Which frontend pages call the API `/orders/:orderId`?
3. Find all API consumers of the `/admin/orders` creation endpoint
4. How many enums and structs have been indexed? (`get_knowledge_stats`)
5. Traverse the graph from `OrderAPIs.getOrder` in the outgoing direction

---

## CROSS-DOMAIN / MEMORY

### Session 19 — Multi-tool Query
1. What is the name of org ID 10? How many completed orders does it have this month?
2. Who is driver ID 225324? Do they have any active orders right now?
3. Who is the customer and org for order 1348180?
4. *(follow-up)* Look up more details about that organization
5. statusCd=5 is Cancelled — list the 3 most recently cancelled orders for org ID 10

### Session 20 — Memory & Context Follow-up
1. *(follow-up)* From that list, which handlers are related to "driver"?
2. *(follow-up)* Show the handler context for the first driver-related handler
3. Is business registration number `1234567890` valid?
4. *(wrap-up)* Summarize: how many order types and payment methods does the system support?

---

## Coverage Map

| Session | Tools Covered |
|---------|--------------|
| 1 | `get_order_detail` |
| 2 | `get_orders_admin_panel`, `submit_order` |
| 3 | `get_order_payment_status`, `get_order_cancel_fee` |
| 4 | `get_order_history` |
| 5 | Multi-turn order memory |
| 6 | `search_users` |
| 7 | `search_organizations` |
| 8 | `search_branches` |
| 9 | `list_admin_roles`, `list_admin_departments`, `list_admin_menus`, `get_admin_permissions`, `get_accessible_menu_tree` |
| 10 | `get_driver`, `search_drivers` |
| 11 | `get_vehicle_pools` |
| 12 | `calculate_driver_fare` |
| 13 | `get_vehicle_prices` |
| 14 | `get_addresses`, `search_api_addresses`, `search_api_address_details` |
| 15 | `lookup_enum`, `explain_status` |
| 16 | `search_endpoints`, `get_handler_context`, `list_available_docs` |
| 17 | `search_codebase` |
| 18 | `find_api_consumers`, `traverse_graph`, `get_knowledge_stats` |
| 19 | Cross-domain multi-tool |
| 20 | Memory / context follow-up |
