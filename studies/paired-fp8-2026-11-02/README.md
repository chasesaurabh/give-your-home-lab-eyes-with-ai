# Same-checkpoint online FP8 comparison — November 2, 2026

306 actual requests, unchanged raw replies, original synthetic inputs and an archived evaluator. The six-case development check passed before these evaluations. This is development research, not a finished book release.

The comparator is the unchanged BF16 pair in `../large-vision-2026-11-02/runs/qwen35-27b-structured001` and `qwen35-27b-challenges001`. Both use checkpoint fc05daec18b0a78c049392ed2e771dde82bdf654, vLLM0.30.0, the same GPU, fraction0.75, context8192, one sequence, eager mode, cache dtypeauto, schema, prompts, pixels and repeat ordering. The new run adds online `--quantization fp8`; it does not use a separate fine-grained block-FP8 checkpoint. Kernels, cache capacity and run timing differ. Repeated-input caching applies.

| Configuration | Controlled strict /180 | Label challenges strict /126 |
|---|---:|---:|
| BF16 | 156 | 108 |
| Online FP8 | 174 | 108 |

See comparison.json for task/group failures, independently recomputed strict scores, the separately prespecified power-only formatting score, timings and 200 ms total-device samples. Never normalize IDs into correctness. These are 60/42 synthetic cases repeated 3 times; repeats are not independent examples.

Logged model-loading allocations were 51.1GiB BF16 and 28.06GiB onlineFP8. Logged availableKV allocations were 18.2GiB and 41.44GiB. These are startup-log components, not minimum-device requirements. With the same allocation fraction, lower model allocation permits a larger cache; total device allocation does not halve.200ms samples can miss short peaks and include other device activity. One sequence is not a concurrency test. No CPU offload was requested.

Offline verification from the repository root:

```bash
python experiments/verify_study.py --study studies/paired-fp8-2026-11-02
```

The protocol was recorded before FP8 startup. Model compatibility was established by actual startup/inference. Preserve both the original comparator and any failures. Code/fictional inputs use MIT; model and dependency licenses remain separate. No book prose, cover, private documents, model weights or font binaries are included.
