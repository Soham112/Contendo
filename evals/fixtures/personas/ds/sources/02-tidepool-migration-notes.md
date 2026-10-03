---
title: Tidepool feature store migration notes
source_type: personal_note
memory_context: work
---
Tidepool is the internal feature store at Fernhollow Logistics. We moved to it from a folder of nightly SQL scripts that each model team copied and modified.

Migration took eleven weeks instead of the planned four. Most of the time went into agreeing on definitions. "Shipments last 7 days" had three versions: by pickup date, by delivery date, and by booking date. Kestrel used booking date. The pricing model used pickup date. Nobody knew.

Rules we settled on:
- Every feature has one owner and a written definition.
- Point-in-time correctness is enforced by the store, not by each team.
- A feature with no consumer for 90 days is archived.

Honest assessment: the feature store itself was the easy part. The hard part was getting two teams to admit they had been computing different things under the same name. I would only do this again once at least two teams share features. Before that it is overhead.
