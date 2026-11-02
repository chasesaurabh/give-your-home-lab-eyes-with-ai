"""Pinned identities used in the book's measured development runs."""
PROFILES = {
    '2b': dict(repo='Qwen/Qwen3.5-2B',revision='15852e8c16360a2fea060d615a32b45270f8a8fc',extra=[]),
    '8b': dict(repo='Qwen/Qwen3-VL-8B-Instruct',revision='0c351dd01ed87e9c1b53cbc748cba10e6187ff3b',extra=[]),
    '27b': dict(repo='Qwen/Qwen3.5-27B',revision='fc05daec18b0a78c049392ed2e771dde82bdf654',extra=[]),
    '27b-fp8': dict(repo='Qwen/Qwen3.5-27B',revision='fc05daec18b0a78c049392ed2e771dde82bdf654',
                   extra=['--quantization','fp8','--kv-cache-dtype','auto']),
    '122b': dict(repo='nvidia/Qwen3.5-122B-A10B-NVFP4',revision='98915d837c4e7c87ac8296d02e89de19b3207e6d',
                extra=['--quantization','modelopt_fp4','--kv-cache-dtype','fp8']),
}
