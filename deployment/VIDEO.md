# File-video evidence workflow

This is a local file workflow, not live-camera surveillance. Select only clips you are authorized to process. The worker ignores audio and sends nothing over a network. The model stage is separate.

Build the CPU image from the repository root (internet is needed for the build):

```bash
docker build -t homelab-vision-tools -f deployment/Dockerfile.tools .
python deployment/run_video_container.py --source your-clip.mkv --output runs/video-first --interval 1
```

Open `runs/video-first/result/review.html` locally. The manifest records the source digest, first video stream, duration, decoded frame count, original best-effort presentation timestamps, times relative to the first frame, requested sample times, decoded frame indices and PNG hashes. These timestamps are not recording dates. Rotation metadata is retained but autorotation is disabled; inspect rotated media before downstream use. The code selects the first decoded frame at or after each requested time and deduplicates repeated selections. It never labels a requested time as an observed time.

Supported containers are MP4/MOV, Matroska and AVI with codecs supported by the installed FFmpeg build. Inputs must be local files, at most 256 MB, with a known positive container duration no longer than 120 seconds, dimensions at most 8 million pixels and no more than 20,000 decoded frame records. Sampling is at least 0.1 seconds and at most 120 selected frames. Shorten the clip or increase the interval when a bound is exceeded; do not remove all limits. PNGs fit within 1280×1280 without changing aspect ratio. Container duration can include a nonzero start offset; the manifest separately records first source timestamp and last relative frame timestamp. The conservative duration limit may reject such a file even if its relative span is short.

The Docker wrapper uses network none, read-only root, a read-only input file/code mount, a new output directory, user10001, dropped capabilities,2GBmemory,2CPUs and a512MBtemporary filesystem. FFprobe/FFmpeg invocations have120second limits; the whole worker has420seconds. The selected input is copied into a bounded private snapshot before hashing/decoding. This reduces changing-input ambiguity. Resource limits and protocol restrictions reduce exposure but do not prove a media decoder free of vulnerabilities. On Linux, arrange write permission for user10001 on the chosen output directory.

`review_required` is a complete decode awaiting inspection. Failed/interrupted output must not be treated as complete evidence. The temporary snapshot is removed; retained outputs contain derived frames and metadata. A sparse sample cannot establish that nothing occurred between frames.

## Original six-second demonstration

Generate fictional frames with a local TTF file (do not distribute font binaries):

```powershell
python experiments/make_video_fixture.py --output runs/video-fixture --font C:/Windows/Fonts/arial.ttf
$framesPath = (Resolve-Path runs/video-fixture).Path
docker run --rm --network none --read-only --cap-drop ALL --user 10001:10001 --memory 1g --cpus 2 --entrypoint ffmpeg --mount "type=bind,source=$framesPath,target=/fixture" homelab-vision-tools -v error -nostdin -n -framerate 10 -i /fixture/%04d.png -c:v ffv1 -level 3 -threads 2 /fixture/alert.mkv
python deployment/run_video_container.py --source runs/video-fixture/alert.mkv --output runs/video-sparse --interval 1
python deployment/run_video_container.py --source runs/video-fixture/alert.mkv --output runs/video-dense --interval 0.2
```

On November2,2026, the tested FFmpeg5.1.9 worker decoded6samples at1second intervals and30samples at0.2second intervals. The fictional alert appears at2.2≤t<2.6seconds. Sparse sampling retained no alert frame; dense sampling retained frames at2.2and2.4seconds. All36decoded PNGs matched the corresponding original pixels exactly, and all source timestamps matched the fixture. This validates the measured clip and configured sampler, not general event recall, camera performance, or model recognition. No VLM was used to establish those facts.

For syntax and timestamp fields see [FFprobe](https://www.ffmpeg.org/ffprobe.html) and [FFmpeg select filter](https://ffmpeg.org/ffmpeg-filters.html#select_002c-aselect). The project tests the installed version; online documentation can describe newer versions.

A separate six-frame variable-rate fixture started at source timestamp 10 seconds. Encoded timestamps were 10.000, 10.100, 10.199, 10.300, 10.550 and 10.800 seconds. At a 0.2-second requested interval, the worker selected relative times 0, 0.3, 0.55 and 0.8 seconds, preserving both requested and observed times. All four selected images matched their original pixels. The 10.199 timestamp came from FFmpeg floating-point `setpts` arithmetic; the actual encoded frame was just before the requested 0.2-second boundary. A deliberately malformed file failed with `failed_or_interrupted` in its manifest and could not be treated as complete evidence.

## Describe and search the selected frames

The CLI provides `analyze-video BUNDLE --model ALIAS --output NEW_DIRECTORY` and `search-video "query" ANALYSIS_DIRECTORY`. These use the separate loopback VLM client. Each response retains its frame, timestamp, source hash and raw provider output; search returns literal token matches in descriptions and visible-text proposals. The full run remains incomplete if any frame request fails.

Actual122BNVFP4 integration used the same concise prompt and256-token budget on both samples. All6sparse and30dense main-status transcriptions matched the fixture exactly. Searching `fan stopped` returned no sparse result and dense results at2.2and2.4seconds. The original, more verbose six-frame trial is also retained; it is not mixed into the concise-prompt comparison. This is one simple synthetic clip. Search matches still require checking the retained frame; they do not establish semantic similarity, continuous event duration or absence of events between samples.
