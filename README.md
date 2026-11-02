# Give Your Home Lab Eyes with AI

Local vision applications and reproducible experiment tools for the book of the same name.

**Development companion for the second edition.** Current code provides image-to-structured proposals, PDF/OCR evidence with page-cited search and answer proposals, bounded video decoding with per-frame descriptions and timestamp-linked search, source-bearing Markdown search, and controlled evaluation scripts. The full project and model study remain under development. This is not the frozen book release. A verified edition-2 book link and immutable release tag will be added when available.

Code is MIT licensed. Model weights and dependencies have separate licenses. Book text, covers, private documents and model weights are excluded.

## Install and test

Use Python 3.12 in a fresh virtual environment. From the repository directory:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use synthetic inputs and a local HTTP fixture server. They do not prove model accuracy or require a GPU.

## Start the tested small-model server

This path requires an NVIDIA GPU, a compatible driver, working Docker GPU support, and Linux containers (Docker Desktop/WSL2 on the tested Windows workstation). Download the public model to a directory outside Git:

```bash
python -m pip install huggingface_hub==1.32.0
python deployment/download_model.py --output models/qwen35-2b
```

The download pins Qwen/Qwen3.5-2B revision `15852e8c16360a2fea060d615a32b45270f8a8fc`. Review its [model card and license](https://huggingface.co/Qwen/Qwen3.5-2B). Downloading requires internet; subsequent inference uses the offline model mount.

PowerShell, from this repository:

```powershell
docker run --name homelab-vision-2b --gpus all -d -p 127.0.0.1:18104:8000 `
  --mount "type=bind,source=$((Resolve-Path models/qwen35-2b).Path),target=/model,readonly" `
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 `
  vllm/vllm-openai:v0.30.0 /model --served-model-name vision-2b `
  --max-model-len 8192 --max-num-seqs 1 --gpu-memory-utilization 0.20 --enforce-eager
docker logs -f homelab-vision-2b
```

For bash use `--mount "type=bind,source=$(pwd)/models/qwen35-2b,target=/model,readonly"` and backslashes instead of PowerShell backticks. This configuration was tested on an RTX PRO 6000 Blackwell with 97,887 MiB total device memory. A 0.20 utilization setting is a fraction of that device, **not a minimum-GPU claim**. Smaller-GPU settings are being measured; do not assume this allocation is suitable for another GPU.

Wait for server readiness. Loading may take minutes. Stop with `docker stop homelab-vision-2b`; resume with `docker start homelab-vision-2b`. Do not create another server on an occupied port.

## Read an image

```bash
homelab-vision analyze fixtures/source/status-panel.png --task describe --model vision-2b --output runs/status-first
```

Use your deliberately selected equipment-label image with `--task label`. The application normalizes the image, hashes source and derivative, checks model identity, and requests schema-constrained output from a loopback endpoint. It saves `input.json`, a normalized PNG, and `proposal.json` in a **new** output directory. Use a different output directory for every attempt.

`review_required` is intentional. Compare each field with the image before using it. Incomplete or invalid output fails the command; it is never silently repaired. The input record remains for diagnosis. This code never runs commands found in an image or automatically changes inventory from model output.

The client disables HTTP proxies/redirects and accepts only literal `127.0.0.1` or `::1`. This is a single-machine reference, not an authenticated multi-user service. Input limits do not sandbox decoders or guarantee that an independently configured server has no network access. Protect saved outputs as you would source images.

## Search text with citations

```bash
homelab-vision search-text "storage utilization" fixtures/source/maintenance-sheet.md fixtures/source/untrusted-note.md
```

Results include source hashes and line locators. This BM25 baseline returns source excerpts, not generated answers. No matches yields `not_found`. Instruction-like text warnings are a narrow heuristic, not a complete prompt-injection defense.

## Reproduce controlled experiments

Supply a local TrueType font. Do not redistribute a proprietary font binary. Example PowerShell commands:

```powershell
python experiments/make_suite.py --help
python experiments/make_label_challenges.py --font C:/Windows/Fonts/arial.ttf --output runs/label-challenges
python experiments/evaluate.py --suite runs/label-challenges --output runs/label-results --model vision-2b --structured --sample-gpu
```

Generators record hashes and ground truth. Inspect inputs before evaluating. The runner records raw responses, strict field scores and latency. `--sample-gpu` requires `nvidia-smi`; it samples total-device memory every 200 ms, may miss brief peaks, and includes other activity. Repeated-input caching prevents treating these times as uncached throughput. Three repeats of one image are not three independent examples.

Keep prompt-only and `--structured` results separate. A schema does not make wrong values correct or prevent output-budget exhaustion. Keep failures in the denominator. The [initial study](studies/initial-vision-2026-11-02/README.md) includes 846 actual responses and original fictional inputs. Verify all hashes and recompute scores offline with `python experiments/verify_study.py`. Later models may need `--thinking off`; template defaults are not identical across model sizes.

The separate [large-model study](studies/large-vision-2026-11-02/README.md) adds 648 actual 27B/122B request records, including context-limit and server failures. Its verifier command, configurations and limitations are in that study's README. Model download/start profiles are documented in [MODELS.md](deployment/MODELS.md). Neither study establishes general accuracy or the largest possible model for a GPU.

The [context follow-up](studies/context-followup-2026-11-02/README.md) reran the 36-request 122B workload with a 40,960-token configured context. All requests completed with exact fields and no errors. It is a remedy test after known 8,192-context failures, not held-out accuracy; the original failed run remains published.

## PDF pages and local OCR

See [the document workflow](deployment/DOCUMENTS.md) for native page preparation and a network-disabled CPU OCR container. It includes a portable wrapper, exact limits, page/word provenance, synthetic fixtures and observed results. The converter routes pages for review; it does not automatically accept document facts.

## Scope

See [the video workflow](deployment/VIDEO.md) for the restricted decoder and original short-event experiment. Sparse and dense samples were actually decoded and checked against source pixels and timestamps. This is file-video evidence, not a live-camera or general event-detection benchmark.

- `src/homelab_vision`: image normalization, model adapter, contracts, lexical retrieval, confirmation-gated inventory primitive, policy, lineage, frame-sampling primitives.
- `experiments`: original fixture generators and evaluator.
- `fixtures/source`: fictional examples.
- `tests`: deterministic boundary and local HTTP contract tests.

The [inventory workflow](deployment/INVENTORY.md) now connects a label proposal to an explicit review, revision-checked transaction, history-preserving rollback and database backup. Its local confirmation is not remote authentication. Semantic retrieval, live-camera monitoring and autonomous repair are not implemented in this snapshot. See `TESTED_ENVIRONMENT.md` and `THIRD_PARTY.md`.

[Investigation packets and combined search](deployment/PROJECTS.md) connect a screenshot observation to selected manuals and search PDF/video evidence together while preserving page citations and frame timestamps. These commands do not generate a diagnosis or execute repairs.
