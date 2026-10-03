# Interview demo

The updated demo can open Ctrl/Cmd+K, add two products to the persistent comparison tray, choose a real sibling configuration on PDP, and ask a contextual product question. In the assistant, use 'Which is better for React development and occasional gaming?' to demonstrate the grounded buying brief, 'Add the cheaper one' for real cart mutation, and 'Take me to checkout' to show navigation. Explain that missing benchmarks/battery data are qualified rather than invented.

Use a disposable local portfolio account and fictional address. No real payment information is needed.

Before presenting, verify the backend and frontend are running against `shopsmart_portfolio`, migrations are current, product images load, and the exact demo phrases work. The seed's intended catalog size is not a substitute for a live database count.

1. Open the homepage, interact with discovery, and browse a database category.
2. Search laptops under ₹60,000; show that every result respects the bound.
3. Open a product and explain API-supplied image/specification data.
4. Sign in and ask the assistant to show laptops under ₹60,000.
5. Compare the first two. Point to current product values and structured comparison.
6. Ask which is cheaper, then add that result to the cart using a supported phrase.
7. Ask for offers and apply an eligible database coupon. Demonstrate an invalid coupon.
8. Open the real cart and explain the server quote.
9. Checkout with a fictional address; open order history and show snapshots.
10. Explain one ownership test and one idempotency test.

For the code tour, follow `OrderService.checkout` in `backend/src/services/order_service.py`. Discuss row locks, a second idempotency lookup after waiting, promotion reevaluation, stock decrement and commit.

For the AI tour, follow `CommerceAssistantService.answer` in `backend/src/services/commerce_assistant.py`. Show owned conversation lookup, deterministic intent and authoritative result hydration.

Keep a fallback path through the conventional catalog/cart UI if an external generation provider is unavailable. Describe the fallback honestly. Use the verified screenshots and current test evidence; do not present planned journeys as completed.
