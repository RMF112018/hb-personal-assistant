# Procore Noise Metric Contract

## Purpose

Identify whether Procore-derived candidates are over-prioritized or generating clutter.

## Inputs

- ranked candidates where `source_family`, `candidate_family`, or `section_key` indicates Procore;
- source-ref count/hash metadata;
- lifecycle outcomes;
- section/rank position;
- Procore candidate family/signal type metadata from safe rows only.

## Metrics

- exposed Procore candidate count;
- accepted/rejected/snoozed/ignored/suppressed/merged counts;
- top-rank Procore rejected/ignored count;
- Procore noise score;
- noisy family/signal-type list;
- safe threshold-tuning recommendation.

## Guardrail

Never hide or suppress Procore candidates automatically. The output is a tuning recommendation only.
