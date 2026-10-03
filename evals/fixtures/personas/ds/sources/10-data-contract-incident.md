---
title: Upstream schema change that broke Tidepool
source_type: personal_note
memory_context: work
---
Incident note. An upstream booking team at Fernhollow Logistics renamed a column from booking_ts to booked_at. The Tidepool ingestion job did not fail; it filled the feature with nulls, and the null-handling default was zero.

For six days Kestrel saw zero recent bookings for one region and forecast almost no trucks. A depot manager caught it because the number looked absurd, not because any alert fired.

Fixes: a data contract between the booking team and Tidepool listing column names, types, and freshness, checked in CI on both sides; ingestion now fails loudly on schema mismatch; and a "forecast sanity" alert compares Kestrel output to the same weekday last year and pages if it drops more than 60 percent.

I used to think data contracts were paperwork. They are cheaper than a week of wrong trucks.
