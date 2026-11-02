# Context expansion follow-up — November 2, 2026

The earlier 122B workload diagnostic at 8,192 context tokens completed 23 of 36 requests, with twelve explicit context-limit HTTP 400 rejections and one server HTTP 500. All attempts remain in the separate large-model study. This follow-up was planned after seeing those failures; it is a diagnostic remedy test, not held-out accuracy.

The same pinned NVIDIA 122B NVFP4 checkpoint, upstream vLLM 0.30.0 image, FP8 KV cache, 0.92 GPU fraction, one sequence and eager mode were restarted with maximum context 40,960. The server became ready after 1,020.625 seconds. The FP8 uncalibrated-scale warnings remained. No CPU offload was requested.

All 36 requests completed with exact expected fields and zero request errors. The workload is three resized versions of one original development label (640/1280/2560 maximum edge), supplied one/two/four/eight times, with three repeats. Resizing adds no new source detail; repeated copies are not distinct documents. The largest input used 33,996 prompt tokens. This does not establish arbitrary long-document accuracy, general maximum capacity or concurrent throughput.

Maximum sampled total-device use was 95,265 MiB on a device reporting 97,887 MiB. Samples every 200 ms include reservations and other activity and may miss brief peaks. Very little headroom remained. Timings involve repeated-image caching and a restarted server; do not treat the two runs as an unbiased speed comparison. The previously observed cache failure did not recur in this run; that does not prove its underlying cause is fixed.

From the repository root:

```bash
python experiments/verify_study.py --study studies/context-followup-2026-11-02
```

Original fixture pixels and actual response bytes are preserved. Hashes include the exact evaluator snapshot. Host paths, raw server logs, private documents, book prose, covers and model weights are excluded. The runtime configuration records the tested image identity; model licenses remain separate from the MIT application code and original fixtures.
