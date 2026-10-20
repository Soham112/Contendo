---
title: Dara Okafor: what a refund bug taught us about eval sampling
input_type: youtube
source_type: youtube
title_origin: provided
author: EvalConf
authorship: user_authored
split: dev
tests: a YouTube transcript of the user's own talk on someone else's channel
---
Thanks for having me. I'm Dara, I run Quillmark, and we make Sieve, which is basically a very stubborn way of comparing your support assistant's answers to good ones.

I want to tell you about the worst week we had this year. We shipped a prompt change to our own demo assistant, our suite said 94%, and for three days it told people refunds took a month. A customer caught it. Not us.

So the lesson I want you to leave with is about sampling. Our golden set had forty tickets and none of them were about refunds. We had measured what was easy for us to label. Now we sample from real traffic, weighted by intent, and I ask every customer how they picked their tickets before I ask what their score is.
