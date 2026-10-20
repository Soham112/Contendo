---
title: Sampling is the spec
input_type: file
source_type: article
title_origin: provided
authorship: user_authored
split: dev
tests: the user's own essay uploaded as a file (stored as article)
---
Sampling is the spec

In March our own demo assistant told customers that refunds took 30 days instead of 14. Our eval suite had passed at 94%. The suite had 40 tickets and not one of them was about refunds.

I used to think an eval set was a test. I now think it is a specification, and a sampling plan is how you write it. If you pick the easy-to-label tickets, you have specified that the assistant must be good at easy tickets.

At Quillmark we rebuilt our set from 120 real tickets, weighted by how often each intent appears. It has caught two billing regressions since. When a customer shows me their eval set, my first question is now how they chose it, not how they score it.
