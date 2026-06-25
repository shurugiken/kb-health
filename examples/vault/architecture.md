---
title: Architecture
tags: [reference]
---

# Architecture

Back to [[index]].

Pathfinder reads notes into a cache layer, then builds an inverted index. The
cache layer holds parsed note trees in memory. When a note changes, only its
cache layer entry is rebuilt. The cache layer is the main reason queries stay
fast.
