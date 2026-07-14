# Local eval intake

This directory receives small, redacted connector-local candidates produced by
calibration or regression pressure. It must not contain credentials, browser
state, private pages, raw API payloads, or full runtime reports.

An intake item describes the failing owner surface, minimal safe evidence,
expected invariant, and proposed local suite. It is a candidate, not a verdict
or proof claim. Promotion, scoring doctrine, and central proof authority remain
with `aoa-evals`.

Executable intake generation and validation belong to the connector CLI, local
suites, tests, and root validator. This document carries only the boundary.
