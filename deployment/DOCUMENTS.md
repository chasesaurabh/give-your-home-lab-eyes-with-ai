# Prepare and inspect PDF pages

This development workflow produces reviewable page evidence and a Tesseract OCR baseline. It does not implement the entire document-intelligence application yet.

For native PDF preparation:

```bash
python -m pip install -e ".[documents,test]"
python -m unittest discover -s tests -v
homelab-vision prepare-pdf your-selected-document.pdf --output runs/pages-first
```

Choose a small synthetic document first. Open `runs/pages-first/review.html` locally. Each page pairs its rendered pixels with extracted text. At least 20 non-whitespace text-layer characters yields `text_layer_review`; fewer yields `ocr_or_blank_review`. These are routing heuristics. A broken text layer can exceed the threshold, and a blank page should not be described as a scan containing text. Compare the content yourself.

The manifest records the source hash, page numbers, derivative hashes, dimensions, DPI and proposed route. No page becomes accepted automatically. Encrypted/malformed files are rejected. Defaults limit inputs to 20 MB, 40 pages, 20 million pixels per page and 144 DPI. The CLI runs the PDF worker with a 120-second timeout. A killed worker may leave a `processing` bundle; do not treat it as complete. Input limits are not an operating-system sandbox.

## Local OCR container

Build the CPU tools image from this repository:

```bash
docker build -t homelab-vision-tools -f deployment/Dockerfile.tools .
```

The build downloads dependencies. The portable wrapper mounts the selected page bundle, code and a new output directory, with networking disabled:

```text
python deployment/run_ocr_container.py --bundle runs/pages-first --output runs/ocr-first
```

It records the actual image ID and resource settings in `runtime.json`. The expanded PowerShell form below shows the same controls; use a different new output folder if you already ran the wrapper:

```powershell
New-Item -ItemType Directory runs/ocr-first
docker run --rm --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges --pids-limit 128 --memory 2g --cpus 2 `
  --tmpfs /tmp:rw,noexec,nosuid,size=256m `
  --mount "type=bind,source=$((Resolve-Path .).Path),target=/code,readonly" `
  --mount "type=bind,source=$((Resolve-Path runs/pages-first).Path),target=/input,readonly" `
  --mount "type=bind,source=$((Resolve-Path runs/ocr-first).Path),target=/out" `
  homelab-vision-tools ocr-pages /input --output /out/result
```

The worker verifies PNG hashes and dimensions before invoking Tesseract. It saves raw TSV and `ocr.json`, with words, confidence scores and pixel boxes tied to each page image. Confidence is an engine score, not calibrated probability. Default page-segmentation mode is 3; modes 6 and 11 are explicit alternatives to evaluate on separate runs.

Measured development evidence: Tesseract 5.3.0 recovered the complete normalized text sequence on both pages of an original two-page mixed PDF at 144 DPI. One page held direct text and the other a raster copy of that same synthetic invoice. All word boxes were within the page. This is an integration check on an easy repeated layout, not an OCR accuracy benchmark. Native conversion also routed digital/scanned/mixed/rotated/blank fixtures and rejected encrypted/malformed fixtures.

To ask the local vision model for invoice fields, select a page PNG and run `homelab-vision analyze ... --task invoice --model YOUR_ALIAS --output NEW_DIRECTORY`. Compare proposed fields to the page and OCR; neither result should silently override the other. A rendered synthetic invoice returned `INV-2042`, `USD`, and `69.0` correctly in the tested 2B configuration. Other document layouts remain to be evaluated.

Keep sources and derived text protected. Delete a disposable run directory only after verifying its exact path; no deletion command is executed automatically by these tools.

## Page-cited retrieval

After inspecting the pages and OCR, build a new derived index:

```bash
homelab-vision index-document runs/pages-first --ocr runs/ocr-first/result/ocr.json --output runs/document-index
homelab-vision search-document "invoice total" runs/document-index
```

Omit `--ocr` for a digital-text-only PDF. The index uses text-layer pages or the matching OCR result for pages routed to OCR. It retains page PNGs, original PDF hashes, page numbers, line locators and OCR word boxes. All results remain `review_required`; the routing heuristic is not a factual approval. Missing OCR yields `no_searchable_text_review` rather than invented text. Hashes and the original PDF identity prevent accidentally combining OCR from another source. Search verifies the retained page records and images before returning excerpts.

This baseline uses BM25 over groups of up to eight text lines. Scores are not confidence probabilities. A term can match an irrelevant page; `not_found` means this lexical search returned no excerpt, not that the entire source contains no possible answer. On the actual fictional mixed-PDF fixture, searching `INV-2042 total` returned the OCR page with its correct printed USD69.00 total and separate digital-text excerpts with page/line citations. That integration test does not establish retrieval quality on a larger corpus.

`ask-document "question" INDEX --model ALIAS --output NEW_DIRECTORY` sends normalized images of at most two retrieved pages to the local VLM, saves the retrieved excerpts and image hashes, and restricts citation numbers to supplied pages. A cited answer still needs visual verification. Actual122BNVFP4 probes returned USD69.00with citations to both fixture pages, and null/empty citations for a different invoice ID and an absent delivery address. These are three single integration probes, not a benchmark. The tested server rejected `uniqueItems`; duplicate-citation validation therefore runs in application code. A subsequent first request failed with a logged multimodal-cache mismatch; its preserved deliberate retry succeeded. HTTP error details and incomplete/invalid raw responses are retained rather than silently discarded.
