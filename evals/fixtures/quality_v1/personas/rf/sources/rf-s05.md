---
title: The Ledger migration at Pellucid Logistics
source_type: personal_note
memory_context: work
authorship: user_authored
---
At Pellucid Logistics I was head of platform. In 2021 we moved the shipment ledger from one Postgres table to an event log. It took nine months instead of the planned four.

We rolled back once, in month five, after the new system double-counted 312 shipments during a regional outage. The fix that got us across the line was boring: dual writes to both systems for eight weeks and a nightly reconciliation job that paged someone on any difference.

My lesson was that a migration plan is mostly a plan for how you will know it is wrong.
