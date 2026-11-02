# Third-party boundaries

MIT covers this repository's original code and fictional fixtures. Dependencies, models and fonts retain their own licenses and notices.

- Pillow: HPND-style license; https://github.com/python-pillow/Pillow.
- jsonschema: MIT; https://github.com/python-jsonschema/jsonschema.
- Optional pypdfium2: Apache-2.0/BSD-3-Clause wrapper terms plus PDFium's bundled third-party notices; https://github.com/pypdfium2-team/pypdfium2.
- The CPU tools container includes Tesseract, Poppler, FFmpeg and their dependencies. Keep their installed copyright/license notices. The tested Debian FFmpeg build has GPL features enabled; it is not relicensed by this repository's MIT file. No prebuilt container is distributed here.
- Optional test/fixture tools include ReportLab and pypdf; inspect their distribution notices before redistribution.
- vLLM: Apache-2.0; https://github.com/vllm-project/vllm. Container dependencies have separate notices.
- Hugging Face Hub: Apache-2.0; https://github.com/huggingface/huggingface_hub.
- Qwen3.5-2B and Qwen3-VL-8B-Instruct: review each pinned model's card/license. Weights are not distributed here.
- Fixture generators use a font supplied locally. Font binaries are not included.

No private documents, credentials, personal information, manuscript, cover or model weights belong in this repository. Review experiment outputs before publishing them.
