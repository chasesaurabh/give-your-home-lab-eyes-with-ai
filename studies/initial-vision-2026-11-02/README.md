# Initial local vision study: inputs and actual outputs

Original fictional fixtures and **846 actual model responses**, across five completed configurations/runs. These data accompany a development-stage book revision. They are not a general model leaderboard or an independent population sample.

| Run | Unique cases | Requests | Strict exact |
|---|---:|---:|---:|
| Qwen3-VL-8B, prompt-only JSON | 60 | 180 | 171 |
| Qwen3.5-2B, prompt-only JSON | 60 | 180 | 54 |
| Qwen3.5-2B, schema-constrained | 60 | 180 | 165 |
| Same 2B, smaller memory reservation | 60 | 180 | 165 |
| 2B label challenges, schema-constrained | 42 | 126 | 108 |

Every case is repeated three times. The 180-request rows reuse the same 60 cases; the compact run changes the GPU allocation fraction from 0.20 to 0.09 on the **same 96 GB workstation**, not on a separate smaller card. Inputs are original synthetic labels, invoices, simulated terminals, charts, shape grids and sampled frame sets. They are not photographs of production systems or a decoded continuous-video benchmark.

The schema follow-up deliberately reused inputs after format failures were observed. It is a disclosed regression experiment, not a new untouched holdout. The 2B label challenge family was created and visually inspected before its first model evaluation. Each of its seven groups contains six distinct generated labels, repeated three times. Conditions are not paired identical subjects; between-group differences do not establish a causal effect of the condition.

The strict scorer requires exactly the requested keys and values. Equivalent JSON numbers such as 69 and 69.0 are equal; booleans are not integers. No Markdown fence or prose is stripped. String whitespace remains significant: a power field of `12VDC` does not strictly match `12 V DC`, even though these denote the same voltage. A strict nonmatch is therefore not automatically a factual/visual error. Any normalized-field analysis must be separately labeled and must preserve these original scores.

Covered-identifier challenge cases all failed in all three repeats by substituting the visible model name into the hidden asset-ID field. The other six challenge groups passed their strict checks. This is one narrow failure pattern; the sticker results do not prove protection against arbitrary prompt injection.

## Recheck without a model

From the companion root:

```text
python experiments/verify_study.py
```

The command verifies 983 input/result/configuration/sample file hashes and recomputes every strict score from the preserved response text. The README and hash manifest itself are outside that hash list. No inference or network access is performed.

Each run has an explicit `configuration.json`. Raw reply records are unchanged; the separate public configuration omits private host paths and raw provider permission metadata. No credentials, original user documents, model weights or font binaries are included. Model and runtime licenses remain separate from the MIT-licensed original code/fictional fixtures.

Historical executions recorded evaluator hashes but did not retain exact historical source snapshots. The current evaluator contains later readiness, telemetry, output-mode and transport improvements. Raw requests' task prompts, image hashes, responses and original scores remain available, and the offline verification recomputes the scoring. Future runs also archive their evaluator source. Do not claim byte-identical reruns across runtime, driver, font or model changes.

Memory CSVs sample total-device use every 200 ms and include reservations and other activity; brief peaks can be missed. Missing CSVs mean no continuous sampling was taken. Warm repeated requests may use prefix/multimodal caches, so timings are not uncached throughput measurements. Large-model comparisons and application evaluations are ongoing.
