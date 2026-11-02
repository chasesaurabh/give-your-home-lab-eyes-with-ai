# Give Your Home Lab Eyes with AI

Local vision applications and reproducible experiment tools for the book of the same name.

**Code companion for the second edition.** Version 1.0.0 provides image proposals, PDF/OCR fields and page-cited answers, screenshot investigation packets, reviewed inventory transactions, and timestamp-linked video and combined search. The recorded model studies are complete. The book itself remains in production; this code release does not establish retailer publication. The verified edition-2 book link will be added after publication. See [BOOK_EDITION.json](BOOK_EDITION.json) for the book/code mapping.

Code is MIT licensed. Model weights and dependencies have separate licenses. Book text, covers, private documents and model weights are excluded.

## Install and test

Acquire the tested second-edition code:

```bash
git clone --branch book-v2.0.0 --single-branch https://github.com/chasesaurabh/give-your-home-lab-eyes-with-ai.git
cd give-your-home-lab-eyes-with-ai
```

The tag identifies this code release; the default branch may change. A detached checkout at a tag is expected. The ZIP archive for the same tag is also available from GitHub's tag page.

Use Python 3.12 in a fresh virtual environment. From the repository directory:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[documents,test]"
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

For bash use `--mount "type=bind,source=$(pwd)/models/qwen35-2b,target=/model,readonly"` and backslashes instead of PowerShell backticks. This configuration was tested on an RTX PRO 6000 Blackwell with 97,887 MiB total device memory. A 0.20 utilization setting is a fraction of that device, **not a minimum-GPU claim**. A separately recorded 0.09 allocation completed the controlled 2B suite on the same workstation. That is not a physical smaller-GPU test; measure the intended workload on your device.

Wait for server readiness. Loading may take minutes. Stop with `docker stop homelab-vision-2b`; resume with `docker start homelab-vision-2b`. Do not create another server on an occupied port.

## Read an image

Inspect preprocessing without a model:

```bash
homelab-vision normalize fixtures/source/status-panel.png --max-edge 320 --output runs/normalize-first
```

This writes `input.json` and a normalized PNG, with no inference. The `normalize-v2` policy bounds source bytes/pixels, applies orientation, composites transparency on white, converts to RGB and strips inherited metadata. It records the Pillow version and explicitly does **not** perform ICC color management. Original files remain unchanged and are not automatically copied into the bundle.

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

The `extract-invoice` command adds a model-free five-field review report for the documented labeled invoice family. It preserves direct-text and OCR candidates, draws OCR line boxes, checks arithmetic and path agreement, and retains conflicts without accepting records. See the document workflow for its limits and executed example.

The [OCR preprocessing study](studies/ocr-preprocessing-2026-11-02/README.md) adds 36 actual CPU jobs comparing unchanged, overview and known-template crop inputs. Cropping improved some small-text fields but produced no completely correct small-text records under the declared strict rubric. Verify all recorded inputs and scores with `python experiments/verify_ocr_study.py`. These OCR jobs are separate from the 1,836 published VLM requests.

## Scope

The [diagram transcription study](studies/diagrams-2026-11-02/README.md) adds 108 evaluation requests plus three separate development requests. Complete graph matches were 6/36 for 2B BF16, 15/36 for 27B BF16 and 20/36 for 122B NVFP4 with FP8 cache. All three transcribed the node and group labels correctly on every evaluation request, yet edge errors and record-contract failures remained. Six designs, two paired resolutions and three repeats do not constitute 36 independent diagrams. The study includes every raw reply, synthetic input and offline scorer. Published VLM evaluation requests now total 1,944; OCR jobs and development requests remain separate.

See [the video workflow](deployment/VIDEO.md) for the restricted decoder and original short-event experiment. Sparse and dense samples were actually decoded and checked against source pixels and timestamps. This is file-video evidence, not a live-camera or general event-detection benchmark.

- `src/homelab_vision`: image normalization, model adapter, contracts, lexical retrieval, confirmation-gated inventory primitive, policy, lineage, frame-sampling primitives.
- `experiments`: original fixture generators and evaluator.
- `fixtures/source`: fictional examples.
- `tests`: deterministic boundary and local HTTP contract tests.

The [inventory workflow](deployment/INVENTORY.md) now connects a label proposal to an explicit review, revision-checked transaction, history-preserving rollback and database backup. Its local confirmation is not remote authentication. Semantic retrieval, live-camera monitoring and autonomous repair are not implemented in this snapshot. See `TESTED_ENVIRONMENT.md` and `THIRD_PARTY.md`.

[Investigation packets and combined search](deployment/PROJECTS.md) connect a screenshot observation to selected manuals and search PDF/video evidence together while preserving page citations and frame timestamps. These commands do not generate a diagnosis or execute repairs.


## Paired precision study

The [same-checkpoint online-FP8 study](studies/paired-fp8-2026-11-02/README.md) adds 306 actual requests and preserves the unchanged BF16 comparator. FP8 reduced the logged model-loading allocation, but was slower on recorded medians and did not resolve the similar-character failures. Strict and separately normalized scores, 200 ms total-device samples, raw replies and offline verification are included. This is development evidence, not a general accuracy or smaller-device guarantee.

## Book chapters and projects

| Chapters | Runnable entry points and evidence |
|---|---|
| 1–5 | Installation, `deployment/MODELS.md`, `normalize`, `analyze`, pipeline tests |
| 6–10 | Image transforms, task schemas, original controlled/label model studies |
| 11–15 and 24 | [PDF, OCR, fields, retrieval and answers](deployment/DOCUMENTS.md) |
| 16–19 and 25 | [Screenshot investigation packets](deployment/PROJECTS.md); diagram study |
| 20–23 | [Selected-file video](deployment/VIDEO.md); camera deployment remains a design extension |
| 26 | [Reviewed inventory, rollback and backup](deployment/INVENTORY.md) |
| 27 | [Combined document/video search](deployment/PROJECTS.md) |

The six study directories preserve 1,944 VLM evaluation requests and a separate 36-job OCR comparison. Development and application probes are separate from those evaluation counts. Each study README identifies the offline verifier and its limits. The raw synthetic evidence is not a general model leaderboard.

See [SECURITY.md](SECURITY.md) for boundaries and reporting, [CONTRIBUTING.md](CONTRIBUTING.md) for changes, and [THIRD_PARTY.md](THIRD_PARTY.md) for dependencies and asset rights. The default branch may evolve; use the immutable tag recorded for your edition.
