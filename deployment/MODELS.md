# Pinned research model profiles

These profiles name exact checkpoints; they do not imply equal hardware requirements or causal comparisons of parameter count.

| Profile | Repository | Weight format used | Initial96GB-workstation allocation |
|---|---|---|---|
| `2b` | Qwen/Qwen3.5-2B | BF16 |0.20, then0.09|
| `8b` | Qwen/Qwen3-VL-8B-Instruct | BF16 |0.35|
| `27b` | Qwen/Qwen3.5-27B | BF16 |0.75|
| `122b` | nvidia/Qwen3.5-122B-A10B-NVFP4 | NVFP4 with FP8 KV |0.92|

Revisions are in `model_profiles.py`. All initial tests use upstream vLLM0.30.0, context8192, one sequence and eager mode. The8Bmodel belongs to an earlier model family. NVFP4 compatibility was actually exercised on Blackwell; do not assume a different GPU supports the same kernels.122B-A10Bis a mixture-of-experts model: total parameters, active parameters and stored-weight memory are different quantities.

Download one selected model to a new dedicated directory with adequate disk space:

```bash
python -m pip install huggingface_hub==1.32.0
python deployment/download_model.py --profile 27b --output models/qwen35-27b
python deployment/start_model.py --profile 27b --model-path models/qwen35-27b --gpu-fraction 0.75 --alias vision-27b --dry-run
```

Inspect the printed argument list and mounted checkpoint, then omit `--dry-run` to launch. The published wrapper was also used to launch the 2B profile at fraction 0.09; the advertised endpoint became ready after 191.25 seconds on the test workstation. Equivalent recorded research commands performed the other model launches. The download helper selects a pinned revision, but the launcher does not cryptographically attest every mounted weight file. Do not point a profile at an unrelated model directory. Keep weights outside version control. Review each checkpoint's card and license before using or redistributing it.

The allocation column is a fraction of this workstation's97,887MiB, not a portable recommendation. For example,0.09on a smaller GPU reserves much less memory. Likewise,0.92on the test machine left little practical device headroom with122B. Record actual GPU memory, runtime overhead and workload success. Use the small model path first; do not infer that downloading a larger checkpoint makes it runnable.

The122Btest runtime warned about uncalibrated FP8 attention/cache scale values1.0. Keep that warning in accuracy comparisons. NVIDIA's model card used a different NVIDIA container in its example; the code here records the upstream container actually tested. The controlled study returned 176/180 strict matches and the label challenge study 124/126, with no transport errors in those studies. A separate 36-request resolution/image-count diagnostic produced 23 exact responses, twelve context-limit HTTP 400 rejections and one logged cache-related HTTP 500. Those failures remain in the public large-model study. A longer-context diagnostic is separate follow-up work.

Model sources: [2B](https://huggingface.co/Qwen/Qwen3.5-2B), [8B](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), [27B](https://huggingface.co/Qwen/Qwen3.5-27B), [122B NVFP4](https://huggingface.co/nvidia/Qwen3.5-122B-A10B-NVFP4). Weights are not included in this MIT repository.


## Same-checkpoint online FP8

The `27b-fp8` profile uses the same pinned BF16 checkpoint as `27b` and adds vLLM online `--quantization fp8`, with cache dtypeauto. It is not the separately packaged block-FP8 model. Reuse the already downloaded27B directory:

```bash
python deployment/start_model.py --profile 27b-fp8 --model-path models/qwen35-27b --gpu-fraction 0.75 --context 8192 --name homelab-vision-27b-fp8 --alias vision-27b-fp8 --dry-run
```

Inspect the command, then omit `--dry-run` to launch after stopping your own previous model server and freeing the same port. Actual research used equivalent recorded Docker arguments; this wrapper profile has a separate dry-run check. The profile keeps one sequence and eager execution. Same allocation fraction allows more cache after reducing model allocation; it does not promise a proportionate reduction in total-device memory. See the paired-precision study for observed results and limits.
