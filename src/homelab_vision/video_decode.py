"""Bounded file-video decoding. Run the documented network-disabled worker for media inputs.

Frame indices and best-effort presentation timestamps come from FFprobe; they are
not capture wall-clock times. The first video stream is used; audio is ignored.
"""
from __future__ import annotations

import bisect
import hashlib
import html
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

MAX_BYTES = 256_000_000
MAX_PIXELS = 8_000_000
MAX_DURATION = 120
MAX_FRAMES = 120


def select_frames(frames: list[dict], interval: float) -> list[dict]:
    if not math.isfinite(interval) or interval < 0.1:
        raise ValueError("interval must be finite and at least 0.1 seconds")
    if not frames or len(frames) > 20000:
        raise ValueError("missing or excessive decoded frame metadata")
    pts = [float(frame['best_effort_timestamp_time']) for frame in frames]
    if not all(math.isfinite(t) for t in pts) or any(b < a for a, b in zip(pts, pts[1:])):
        raise ValueError("timestamps must be finite and nondecreasing")
    if any(not 0 < int(f['width']) * int(f['height']) <= MAX_PIXELS for f in frames):
        raise ValueError("frame dimensions exceed the pixel limit")
    relative = [t - pts[0] for t in pts]
    if relative[-1] > MAX_DURATION:
        raise ValueError("clip exceeds the 120-second limit")
    count = math.floor((relative[-1] + 1e-8) / interval) + 1
    if count > MAX_FRAMES:
        raise ValueError("sample exceeds 120 frames; increase interval or shorten the clip")
    selected, seen = [], set()
    for n in range(count):
        requested = round(n * interval, 6)
        index = bisect.bisect_left(relative, requested - 1e-8)
        if index >= len(frames) or index in seen:
            continue
        seen.add(index)
        selected.append(dict(frame_index=index, source_pts_seconds=pts[index],
            timestamp_seconds=round(relative[index], 6), requested_timestamp_seconds=requested,
            selection_reason='first decoded frame at or after requested relative timestamp'))
    return selected


def _bounded_output(command: list[str], work: Path, name: str, limit: int = 4_000_000) -> bytes:
    path = work / name
    with path.open('wb') as out, (work / (name + '.stderr')).open('wb') as err:
        subprocess.run(command, stdout=out, stderr=err, check=True, timeout=120)
    if path.stat().st_size > limit:
        raise ValueError('decoder metadata exceeds byte limit')
    return path.read_bytes()


def decode_video(source: Path, output: Path, *, interval: float = 1.0,
                 ffmpeg: str = 'ffmpeg', ffprobe: str = 'ffprobe') -> dict:
    if not math.isfinite(interval) or interval < 0.1:
        raise ValueError('interval must be finite and at least 0.1 seconds')
    if not source.is_file() or not 0 < source.stat().st_size <= MAX_BYTES:
        raise ValueError('select one local video file of at most 256 MB')
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(state='processing', interval_seconds=interval, frames=[],
        limits=dict(bytes=MAX_BYTES, pixels=MAX_PIXELS, duration_seconds=MAX_DURATION, sampled_frames=MAX_FRAMES),
        notice='Sampled frames cannot establish what happened between them. No audio processing or wall-clock timestamp inference.')
    record = output / 'manifest.json'
    record.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        with tempfile.TemporaryDirectory(prefix='vision-video-') as temp:
            work = Path(temp)
            snapshot = work / 'input.media'
            # Decode the same bounded snapshot that was hashed, not a changing source.
            digest, total = hashlib.sha256(), 0
            with source.open('rb') as original, snapshot.open('xb') as copy:
                while data := original.read(1_048_576):
                    total += len(data)
                    if total > MAX_BYTES:
                        raise ValueError('video grew beyond the byte limit')
                    digest.update(data); copy.write(data)
            manifest['source_sha256'] = digest.hexdigest()
            common = ['-v', 'error', '-protocol_whitelist', 'file,pipe',
                      '-format_whitelist', 'mov,matroska,avi', '-threads', '2']
            probe = [ffprobe, *common, '-select_streams', 'v:0', '-show_streams', '-show_format',
                     '-of', 'json', str(snapshot)]
            info = json.loads(_bounded_output(probe, work, 'info.json'))
            streams = info.get('streams', [])
            duration = float(info.get('format', {}).get('duration', 'nan'))
            if len(streams) != 1 or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
                raise ValueError('requires one selected video stream and a known duration of at most 120 seconds')
            stream = streams[0]
            if not 0 < int(stream['width']) * int(stream['height']) <= MAX_PIXELS:
                raise ValueError('video exceeds pixel limit')
            frame_data = json.loads(_bounded_output([ffprobe, *common, '-select_streams', 'v:0',
                '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time,width,height',
                '-of', 'json', str(snapshot)], work, 'frames.json'))
            selected = select_frames(frame_data['frames'], interval)
            manifest.update(format_duration_seconds=duration, decoded_frame_count=len(frame_data['frames']),
                first_source_pts_seconds=float(frame_data['frames'][0]['best_effort_timestamp_time']),
                last_relative_frame_timestamp_seconds=round(float(frame_data['frames'][-1]['best_effort_timestamp_time'])-
                    float(frame_data['frames'][0]['best_effort_timestamp_time']),6),
                source_dimensions=[stream['width'], stream['height']], audio='ignored')
            (output/'decoded-timestamps.json').write_text(json.dumps(frame_data,indent=2),encoding='utf-8')
            expression = '+'.join(f"eq(n\\,{f['frame_index']})" for f in selected)
            # Disable autorotation to keep geometry explicit. Rotation metadata is recorded.
            manifest['rotation_metadata'] = stream.get('side_data_list', [])
            frame_dir = output / 'frames'; frame_dir.mkdir()
            command = [ffmpeg, '-nostdin', *common, '-noautorotate', '-i', str(snapshot),
                '-map', '0:v:0', '-an', '-sn', '-dn', '-vf',
                f"select={expression},scale=w='min(1280,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease,setsar=1",
                '-fps_mode', 'passthrough', '-frames:v', str(len(selected)), '-threads', '2',
                str(frame_dir / '%04d.png')]
            _bounded_output(command, work, 'decode.stdout')
            paths = sorted(frame_dir.glob('*.png'))
            if len(paths) != len(selected):
                raise ValueError('decoded frame count does not match selection')
            for entry, path in zip(selected, paths, strict=True):
                with Image.open(path) as im:
                    entry.update(width=im.width,height=im.height)
                    im.verify()
                entry.update(image='frames/' + path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for executable in (ffmpeg, ffprobe):
                manifest[Path(executable).name + '_version'] = _bounded_output(
                    [executable, '-version'], work, Path(executable).name + '.version').decode().splitlines()[0]
            manifest.update(state='review_required', frames=selected)
            cards = ''.join(f'<figure><img width="480" src="{html.escape(f["image"])}">'
                f'<figcaption>Selected {f["timestamp_seconds"]:.3f}s; requested {f["requested_timestamp_seconds"]:.3f}s; '
                f'decoded frame {f["frame_index"]}</figcaption></figure>' for f in selected)
            (output / 'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Video frame review</title>'
                '<h1>Review sampled frames</h1><p>' + html.escape(manifest['notice']) + '</p>' + cards, encoding='utf-8')
    except BaseException as error:
        manifest['state'] = 'failed_or_interrupted'
        manifest['error_type'] = type(error).__name__
        raise
    finally:
        record.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest
