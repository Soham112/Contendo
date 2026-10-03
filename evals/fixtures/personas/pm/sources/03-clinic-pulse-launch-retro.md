---
title: Clinic Pulse launch retrospective
source_type: personal_note
memory_context: work
---
Clinic Pulse is Brightloom's analytics page for clinic owners: utilisation by practitioner, no-show rates, and revenue by service. We launched it in March.

What went well: Northgate Health used it in their first week to rebalance practitioner hours, and their owner quoted it in a case study.

What went badly: we launched with twelve charts. Usage data after a month showed owners looked at two, utilisation and no-shows, and ignored the rest. We also shipped without explaining how no-show rate was calculated, and three clinics filed tickets saying the number was wrong. It was right; it just counted late cancellations as no-shows.

Changes: Clinic Pulse now opens on the two charts people use, every metric has a one-line definition on hover, and we added a weekly email summary because owners would not log in to look.

Retro takeaway: ship fewer charts with clearer definitions.
