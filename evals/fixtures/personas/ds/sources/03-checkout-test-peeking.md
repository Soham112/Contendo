---
title: Checkout redesign A/B test and the peeking problem
source_type: personal_note
memory_context: work
---
At Fernhollow Logistics we ran an A/B test on the self-serve booking checkout. The product manager checked the dashboard daily. On day four the new checkout showed a 9 percent lift in completed bookings with p = 0.03, and there was pressure to ship.

We had planned a 21-day test. I asked for the full run. By day 21 the lift was 1.2 percent and not significant. Early peeking with a fixed-horizon test inflates false positives; checking every day for three weeks pushes the real false positive rate far above 5 percent.

Since then: we pre-register the stopping date and the primary metric in the ticket, and if the team wants to look early we use a sequential test with an alpha spending rule. The dashboard now hides p-values until the planned end date. Peeking is a process bug, not a statistics bug.
