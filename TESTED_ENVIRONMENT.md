# Tested environment and evidence

Code version 1.0.0, tested November 2, 2026. The deterministic suite passed 81 tests in the source checkout and a fresh public clone. These test code contracts; model results are recorded separately below.

## Runtime

- Python 3.12 on Windows; Pillow 12.3.0 and jsonschema 4.26.0.
- Inference: Docker Linux containers through WSL2, vLLM 0.30.0, NVIDIA RTX PRO 6000 Blackwell Workstation Edition, driver 582.16, 97,887 MiB reported device memory.
- PDF: pypdfium2 5.14.0. OCR: Tesseract 5.3.0 in the restricted CPU worker. Video: FFmpeg 5.1.9 in the restricted decoder.
- Model profiles and exact download revisions: [MODELS.md](deployment/MODELS.md). Recorded studies cover 2B and 8B BF16, 27B BF16/online FP8, and 122B NVFP4 with FP8 KV cache.

## Reproducible studies

The six study directories preserve 1,944 VLM evaluation requests and 36 separate CPU OCR jobs. Development and application probes are separate. Each README provides configurations, raw records, scoring rules and an offline verifier.

| Study | Evidence |
|---|---|
| [Initial vision](studies/initial-vision-2026-11-02/README.md) | 846 requests, including prompt-only versus structured output and a smaller allocation on the same physical GPU |
| [Large vision](studies/large-vision-2026-11-02/README.md) | 648 requests from 27B/122B configurations, including failures |
| [Context follow-up](studies/context-followup-2026-11-02/README.md) | 36 requests testing a longer-context remedy after known failures |
| [Paired precision](studies/paired-fp8-2026-11-02/README.md) | 306 online-FP8 requests with the preserved same-checkpoint BF16 comparator |
| [Diagram transcription](studies/diagrams-2026-11-02/README.md) | 108 evaluation requests, plus three separate development requests |
| [OCR preprocessing](studies/ocr-preprocessing-2026-11-02/README.md) | 36 CPU jobs comparing unchanged, overview and known-template crop inputs |

## Executed application paths

The workflow guides distinguish actual integration checks from design extensions:

- [Documents](deployment/DOCUMENTS.md): PDF routing, native text, restricted OCR, invoice-field review, indexing and page-cited answers.
- [Video](deployment/VIDEO.md): constant/variable-rate decoding, sparse/dense sampling and timestamp-linked search on a fictional clip.
- [Inventory](deployment/INVENTORY.md): proposal review, revision-checked transactions, rollback and backup reopening.
- [Investigation and combined search](deployment/PROJECTS.md): screenshot evidence, escaped manual excerpts and joined PDF/video results.

## Interpretation limits

All model measurements come from one workstation and original synthetic inputs. Allocation fractions are not minimum-memory requirements or physical smaller-GPU tests. The 122B configuration is the largest tested here, not proof of the largest possible model. FP8 KV-scale warnings and failed requests remain in the evidence.

Repeated examples are not independent samples. Sampled memory is total-device use at 200 ms intervals and may miss peaks; request times can include caching effects. Different families and precisions do not establish a causal model-size ranking. Schema-valid output can still be factually wrong. The context remedy reused known cases and is not held-out accuracy.

These tools require human review. Live-camera monitoring, semantic embeddings, autonomous repair and remote multi-user authentication are outside this snapshot. See [SECURITY.md](SECURITY.md) and the individual study limitations before adapting the code.
