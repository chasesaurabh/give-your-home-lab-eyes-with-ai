# Small graph transcription — November 2, 2026

108 actual evaluation requests and three separate development requests. Six original graph designs, each at two paired resolutions, each requested three times per model. Development has a separate two-node image. Raw responses and failures are unchanged. This is development research, not the final book release.

The primary scorer ignores array order only. Duplicate values, changed characters, wrong types and extra keys fail. The original order-sensitive harness score is retained. Node transcription, directed/undirected/dashed edges, group membership, exact legend meaning and the visible TLS label are scored separately. No general architecture, real-diagram or security-reasoning claim follows.

The target represents a directed dashed connector in both directed_edges and dashed_edges. In all twelve 27B dashed/annotated evaluation requests, the model recorded the dashed connectors correctly in dashed_edges but omitted them from directed_edges. This is a record-contract mismatch; the raw output does not justify saying those connectors were visually unseen. The original prompt was not changed after inspecting results. Other preserved failures include a reversed vertical arrow and a crossing connector reported without direction. Inspect per-field records rather than attributing every whole-record failure to visual recognition.

Frozen protocol preceded inference. The initial 2B server mount pointed to the parent of the checkpoint, lacked config.json and exited without serving. The corrected, separately named startup used the actual pinned revision directory. Its evaluation was not a retry of failed model requests. The one development request per model checked HTTP completion and schema validity; its semantic accuracy remains in the records and was not used to retune the task.

All configurations used vLLM 0.30.0, context 8192, one sequence, eager execution, temperature zero, thinking disabled and a 512-token output cap. The 122B lane used NVFP4 weights and FP8 cache with logged uncalibrated-scale warnings. These model/precision differences do not isolate parameter count as a cause. Client timings include request processing and possible repeated-input caching. GPU samples are total-device observations every 200 ms; they include reservations and other activity and can miss short peaks. Startup is not an uncached-storage benchmark.

Offline verification from the companion root:

```bash
python experiments/verify_diagram_study.py --study studies/diagrams-2026-11-02
```

The verifier checks every published artifact hash, input identity, complete request coverage and both scores from raw replies. Original synthetic SVG/PNG fixtures and code are MIT. No font binaries, model weights, book prose, covers, private documents or raw host logs are distributed. SVG refers to locally available fonts; rerendering with another font can change pixels. Use the recorded PNG bytes to reproduce the inference input.
