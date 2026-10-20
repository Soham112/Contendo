---
title: The refund-policy regression Sieve missed
source_type: personal_note
memory_context: work
authorship: user_authored
---
In March 2026 we shipped a prompt change to Sieve's own demo assistant. Our eval suite passed: 94% on the golden set. For three days the assistant told customers that refunds took 30 days instead of 14. A customer caught it, not us.

The golden set had 40 tickets and none of them asked about refunds. We had measured what was easy to label, not what customers actually asked.

What we changed: we rebuilt the set from a random sample of 120 real tickets, weighted by how often each intent appears. Since then the suite has caught two regressions before release, both in billing answers. I now say "an eval is only as good as its sampling" in every customer onboarding.
