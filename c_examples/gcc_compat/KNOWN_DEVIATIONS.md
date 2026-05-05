# Known Deviations (Temporary)

This file tracks known differences from full C11 + libc behavior while Mnemo is
in "syntactic 1:1 + partial runtime" mode.

## Current known deviations

- Full libc formatting is not complete in `printf` (length modifiers and many
  libc formats still missing, but `%x` and basic `%p` are now supported).
- Some pointer/type combinations are still subset-limited during lowering.
- Some operator families still need full parity in all expression contexts.
- `struct`/`union` support is not fully equivalent to a native C compiler in all
  call and assignment patterns.

## Policy

- Every deviation must have:
  - owner
  - target milestone
  - dedicated parity tests
- Deviation entries should be removed when parity is implemented.

## Tracking template

Use this template for each item:

```text
ID: DEV-XXX
Area: parser|typing|lowering|runtime
Current behavior:
Expected gcc behavior:
Files likely involved:
Tests added:
Milestone:
Status: open|in-progress|closed
```
