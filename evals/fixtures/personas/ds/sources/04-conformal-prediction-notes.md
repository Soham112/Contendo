---
title: Notes on conformal prediction intervals
source_type: article
memory_context: learning
---
Learning notes. Conformal prediction wraps any point model and produces intervals with a coverage guarantee, assuming exchangeability.

Split conformal in four steps: train the model on one split; compute absolute residuals on a calibration split; take the (1 - alpha) quantile of those residuals with a small finite-sample correction; add and subtract it from new predictions.

Caveat for forecasting: time series are not exchangeable. Adaptive conformal methods update the quantile online as errors come in, which handles drift better. I want to try this on Kestrel's depot intervals instead of the quantile regression we use now.
