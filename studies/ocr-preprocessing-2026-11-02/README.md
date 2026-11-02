# OCR preprocessing: actual CPU comparison

Thirty-six actual Tesseract 5.3.0 English PSM6 jobs on November2,2026. Six clear and six small-text original fictional labels, each unchanged, normalized to max-edge320, and cropped using known fixture coordinates. The crop is not automatic detection. No GPU or VLM is involved.

The protocol was recorded before execution. Inputs were used in the earlier vision study; this is a descriptive follow-up, not a new held-out accuracy set. One job per recipe/image, no repeatability claim. Recorded seconds include Docker startup, not isolated OCR engine time.

| Group | Recipe | Exact records | Correct fields |
|---|---|---:|---:|
| clear | original |6/6|24/24|
| clear | overview |0/6|9/24|
| clear | crop |6/6|24/24|
| small text | original |0/6|14/24|
| small text | overview |0/6|0/24|
| small text | crop |0/6|17/24|

Zero job errors. Strict nonmatches include punctuation, case and power spacing, not only semantic character loss. No identifier repair. See PROTOCOL.md and the executed runner.py for exact parsing rules.

`run/results.json` is the original completed record. Submitted images are retained at its relative paths under run/. `raw-ocr.json` preserves decoded TSV stdout and stderr in JSON strings; the original TSV byte hashes are included (the experiment used Windows UTF-8 text writes). All source images in the original42-case manifest are retained for provenance, although only12were used here. No font binary, model weights, private input or host path is included.

From the repository root, verify hashes and rescore without Docker:

```text
python experiments/verify_ocr_study.py
```

To rerun, build the tools container as documented in deployment/DOCUMENTS.md, then:

```text
python experiments/compare_label_ocr.py --suite studies/ocr-preprocessing-2026-11-02/inputs/labels --output runs/ocr-comparison
```

The run record pins the actual Docker image ID. Rebuilding the current Dockerfile does not promise identical dependency bytes. The overview used the companion normalize-v2 policy with Pillow12.3.0. Originals960x640, overview320x213, native crop550x285 from [100,160,650,445], right/bottom exclusive. No sharpening or enlargement. The executed runner is retained unchanged; later reusable code can evolve independently.
