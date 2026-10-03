---
title: Kestrel holiday forecast postmortem
source_type: personal_note
memory_context: work
---
Postmortem, written January. Kestrel is the freight demand forecast I own at Fernhollow Logistics. It predicts trucks needed per depot per day, 14 days ahead.

What happened: for the two weeks before Christmas, Kestrel under-forecast demand at the three northern depots by 18 to 26 percent. Depot managers trusted it, booked too few contract drivers, and paid spot rates for the gap. Finance estimated the overspend at roughly 410,000 SEK.

Why: the gradient boosted model learned seasonality from two years of history, but one of those years had a warehouse strike in December that suppressed volume. The model treated the strike year as normal. Our validation split used random weeks, so no December week was ever held out, and offline error looked great.

What we changed:
- Validation now always holds out the most recent peak season.
- We added a holiday-and-disruption flag table that analysts maintain by hand. Strike weeks are flagged and down-weighted.
- Depot managers now see an interval, not a point forecast. The 80 percent interval would have covered the actual demand at two of the three depots.

What I would tell past me: offline metrics answered a question nobody asked. The question was whether December would be right.
