---
title: Wrenlog weekend birdsong classifier
source_type: personal_note
memory_context: personal_project
---
Wrenlog is my weekend project: a small birdsong classifier for recordings from a microphone in my garden.

Pipeline: 5-second clips, mel spectrograms, a small CNN fine-tuned from a pretrained audio model. About 1,900 labelled clips across 14 species, most of which I labelled myself on winter evenings.

Biggest lesson so far: my accuracy jumped from 71 to 84 percent not from model changes but from cleaning labels. About one clip in eight had two birds singing and I had labelled only the louder one. Same lesson as work, smaller stakes.

Next: run it on a Raspberry Pi and log detections to a spreadsheet my partner can read.
