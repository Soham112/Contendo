---
title: Mentoring analysts through SQL reviews
source_type: personal_note
memory_context: observation
---
I review SQL for two junior analysts every week. The pattern: their logic is usually correct, but they rarely state the grain of the output. A query meant to be one row per shipment turns into one row per shipment-stop after a join, and every sum doubles.

Now I ask them to write the grain as a comment on the first line before writing anything else. Review time dropped by about half.
