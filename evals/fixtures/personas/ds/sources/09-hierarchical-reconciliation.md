---
title: Hierarchical forecast reconciliation notes
source_type: article
memory_context: learning
---
Learning notes on reconciling forecasts across a hierarchy, for example depot, region, and national totals.

Independent forecasts at each level do not add up. Bottom-up sums the lowest level and is noisy; top-down splits the total by historical proportions and misses local shifts. Optimal reconciliation (MinT) combines all levels using the forecast error covariance and usually beats both.

Practical note: MinT needs a decent estimate of the error covariance, and with many series a shrinkage estimator is needed. Worth trying for regional freight planning, where regional and depot numbers currently disagree.
