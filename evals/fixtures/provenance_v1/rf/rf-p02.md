---
title: Why we didn't build a spreadsheet eval
input_type: url
source_type: article
title_origin: provided
authorship: external
split: dev
tests: I1 + first person: a competitor's blog in 'we' that names Sieve and Quillmark
---
When we started Evalyze, every customer asked us the same thing: why not just do what Sieve does and compare answers to a spreadsheet of good replies? Quillmark has done well with that approach and I respect it.

We went the other way. Our first customers were banks with thousands of intents, and nobody there could write a golden answer for each one. So we built adversarial test generation first and human review second.

I won't pretend it was the right call for everyone. Our onboarding takes three weeks; theirs takes three days. But for regulated teams, generated coverage beat hand-written examples every time we measured it.

Ilya Brandt, CTO, Evalyze
