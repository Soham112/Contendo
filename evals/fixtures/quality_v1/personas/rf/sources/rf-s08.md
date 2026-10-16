---
title: I changed my mind about LLM-as-judge
source_type: personal_note
memory_context: work
---
For most of 2025 I told customers not to use a model to grade a model. My view was that you cannot check a system with a copy of itself.

What changed it: in January 2026 we ran a model judge and two human reviewers over the same 500 conversations. The judge agreed with the humans 86% of the time, about as often as the humans agreed with each other (88%). Where it disagreed, it was usually stricter.

So Sieve now uses a model judge, with a human checking a random 10% sample every week. I still think a judge without that audit is a guess.
