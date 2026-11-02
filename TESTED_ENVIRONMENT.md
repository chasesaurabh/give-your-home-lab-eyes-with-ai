# Development verification

Observed November 2, 2026. This is not the final book release matrix.

- Python 3.12 on Windows, Pillow 12.3.0, jsonschema 4.26.0.
- 34 deterministic tests passed after adding the local HTTP adapter. The fixture server verifies actual local HTTP transport, schema rejection and redirect rejection. This is not a model benchmark.
- Actual Qwen3.5-2B BF16 inference through vLLM 0.30.0 on an RTX PRO 6000 Blackwell Workstation Edition, driver 582.16, 97,887 MiB reported total memory.
- Actual `analyze --task label` integration test returned the four printed fields correctly on one original synthetic fixture. One successful example is not a general accuracy result.
- Controlled suite: 60 original synthetic cases, three repeats each. Qwen3-VL-8B BF16 prompt-only: 171/180 exact. Qwen3.5-2B BF16 prompt-only: 54/180 exact. The same 2B with schema-constrained response format: 165/180 exact. Different model families/configurations do not establish a causal size ranking. The schema follow-up deliberately reused cases after format failures. Raw production evidence is retained; reviewed public exports are pending.
- Tested Docker image ID: `sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90`. Eager execution, 8,192-token context, one sequence, GPU utilization caps 0.20 (2B) and 0.35 (8B). Caps are not measured minimum-memory requirements.

Fresh virtual-environment installation of the code-only export passed all 34 tests and the documented text-search command. The installed image command also completed against the real 2B endpoint, but its description misread the fictional dashboard identifier (`LAE-GW-01` instead of `LAB-GW-01`) and added unsupported grid-line detail. Transport/schema success does not mean factual success. Public clone verification and smaller-GPU settings remain separate checks. Broader models, PDF/OCR, video and applications remain in progress.
