# Contributing

Use Python 3.12 in a fresh virtual environment, install `python -m pip install -e ".[documents,test]"`, and run `python -m unittest discover -s tests -v`. Model-free tests do not need a GPU. Use the exact study inputs and each study's offline verifier to inspect published evidence without inference.

Keep changes small and explain the user-visible problem, boundary affected and actual validation. Add a meaningful regression case for behavior changes. Use synthetic inputs you own or can redistribute; identify their origin and license. Do not commit private files, generated runs, credentials, proprietary font binaries, book prose, covers or model weights.

Do not rewrite frozen study inputs, prompts, scores or failed replies. A new model, scorer, prompt or dataset needs a separately identified study with declared metrics and retained failures. Distinguish deterministic checks, actual inference and untested design suggestions in documentation.

Code contributions are submitted under the repository's MIT license. Third-party dependencies and model weights retain their own terms. Report security-sensitive issues according to SECURITY.md.
