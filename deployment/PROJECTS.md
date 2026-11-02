# Investigation packets and combined search

These are local, single-user workflows. They retain evidence for review and execute no repair commands. No web service, remote authentication, semantic embeddings or generated cross-source diagnosis is implemented.

## Troubleshooting packet

With the small model already running:

```bash
homelab-vision analyze studies/initial-vision-2026-11-02/inputs/controlled/screenshot-00-0.png --task terminal --model vision-2b --output runs/troubleshooting-observation
homelab-vision troubleshoot runs/troubleshooting-observation --manual fixtures/source/camera-runbook.md --question "camera E_ACCESS" --output runs/troubleshooting-case
```

Open `runs/troubleshooting-case/review.html`. The actual 2B fixture request returned camera/E_ACCESS/4, matching the original fictional screenshot. The case snapshots deliberately selected UTF-8 Markdown manuals, verifies screenshot hashes and retrieves line-cited excerpts for your explicit query. The example produced five excerpts; lexical matches can include other error-code sections, so inspect relevance and version. The query is not silently generated from model fields.

The case records creation time, not a verified screenshot capture time. It includes raw observation, image and manual bytes; protect all of them when using real systems. HTML escapes source text and loads no external assets. Up to ten manuals, 2 MB each; question up to 2,000 characters. A failed stage records failure, and no lexical match returns not_found. Instruction-like text warnings are only a heuristic.

## Search selected PDF and video evidence

First follow DOCUMENTS.md and VIDEO.md to create the corresponding indexes. Substitute the actual directories you created:

```bash
homelab-vision search-library fan --document runs/document-demo/index --video runs/video-dense-analysis
```

Repeat `--document` or `--video` to select additional indexes, at most twenty total. Duplicate resolved paths are rejected. Nothing crawls the filesystem. An invalid or changed index fails instead of being silently omitted.

The command preserves PDF page/line citations and video timestamps as distinct evidence types. It interleaves each source's ranked results using `1/(60+rank)`, with source-ID tie breaking. It does not compare raw BM25 scores with token-coverage fractions or claim calibrated relevance. Keep the command with the output so document-1/video-1 can be mapped to the selected paths.

Actual integration searched the fictional invoice and dense 2B video descriptions for fan. The 2B video search found alert samples at 2.2/2.4 seconds despite nonexact status transcriptions; the sparse analysis found no alert. A shared word does not establish that the invoice and video describe the same physical incident.

To exclude a source, omit its argument. That does not delete the original, derivatives, raw replies, saved reports or backups. Deliberate data removal and multi-user authorization are separate responsibilities. A saved hash cannot restore missing evidence bytes.
