# Large-model development study — November 2, 2026

This package contains 648 actual request records, original fictional inputs and recorded runtime configurations. It extends the separate initial study and preserves unsuccessful requests.

| Run | Requests | Strict matches | Request errors |
|---|---:|---:|---:|
| 27B controlled | 180 | 156 | 0 |
| 27B label challenges | 126 | 108 | 0 |
| 122B controlled | 180 | 176 | 0 |
| 122B label challenges | 126 | 124 | 0 |
| 122B resolution/image-count diagnostic | 36 | 23 | 13 |

The controlled set contains 60 original synthetic cases, each repeated three times; the label set contains 42 cases with three repeats. Repeats are not independent examples. The workload diagnostic resizes and repeats one development label: three resolutions, four image counts and three repeats. Interpolation adds no new visual detail. This is a fit/context test, not general accuracy.

All runs use schema-constrained output, explicit thinking off, temperature 0, a 256-token output budget, one scheduled sequence and an 8,192-token context. The 27B model uses BF16; the 122B model uses NVFP4 weights and FP8 KV cache on the same nominal 96 GB Blackwell GPU. Model size, architecture, training, precision and runtime effects are confounded. This is not a causal scaling benchmark.

The 27B controlled run has 18 power-spacing-only nonmatches and six counting failures. Separately normalizing only integer voltage and spacing around `V DC` yields 174/180; its strict score remains 156/180. This rule was recorded before the 27B/122B evaluation, after the earlier 2B/8B runs. The 122B controlled run's four nonmatches are counting errors. On challenges, 27B correctly abstained on 18/18 covered IDs but matched 0/18 similar-character cases; 122B scored 18/18 and 16/18 respectively. Never normalize asset identifiers into correctness.

The workload's twelve HTTP 400 errors explicitly exceed the configured context: 1,280-pixel edge with eight image copies, or 2,560-pixel edge with two, four or eight copies. Its one HTTP 500 occurred after rejected requests. The retained private server log identifies multimodal-cache drift; later repeats succeeded. The public raw error body says only “Internal server error,” so that attribution comes from the separate server log. No out-of-memory error was observed. Every completed request matched its fields. Do not discard the thirteen failures or present 23/36 as visual accuracy.

The 122B runtime warned about uncalibrated FP8 attention/cache scales of 1.0. NVIDIA's model-card example used a different container; these measurements use upstream vLLM 0.30.0. Memory samples were taken every 200 ms, include reservations and other device activity, and may miss brief peaks. Timings include repeated-input caching. Subsequent larger-context testing is a separate follow-up, excluded here.

From the repository root:

```bash
python experiments/verify_study.py --study studies/large-vision-2026-11-02
python experiments/summarize_run.py --run studies/large-vision-2026-11-02/runs/qwen35-122b-structured001 --suite studies/large-vision-2026-11-02/inputs/controlled --output runs/122b-report.json
```

Create the output parent directory first and choose a new report filename. The verifier checks hashes and recomputes strict scores, counting request errors as failures. Exact evaluator snapshots are included where archived and checked against the original run's hash. Each configuration declares whether its snapshot exists.

Font binaries, weights, book prose, covers, private documents and raw host/server records are excluded. Original fixture pixels and raw replies remain unchanged. MIT applies to the repository's original code and fixtures; models and dependencies retain their own licenses.
