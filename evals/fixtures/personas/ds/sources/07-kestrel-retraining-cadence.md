---
title: Kestrel retraining cadence decision
source_type: personal_note
memory_context: work
---
Decision record. Question: should Kestrel retrain nightly, weekly, or on drift?

We tested all three on 18 months of backfill. Nightly retraining was the most accurate on average but made forecasts jumpy, and depot managers lost trust when the 10-day-ahead number changed by 15 percent overnight. Weekly retraining was 2 percent less accurate and far more stable.

Decision: weekly retraining on Sunday nights, with features read from Tidepool so training and serving see identical definitions, plus a drift alarm that triggers an extra retrain if the population stability index on key Tidepool features passes 0.25.

Fernhollow Logistics depot managers care more about stable plans than the last point of accuracy. Optimise for the user of the forecast, not the metric.
