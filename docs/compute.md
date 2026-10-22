# Initial inspection — October 22, 2026

The workspace was empty: no existing code, images, annotations, or repository
instructions were present. No dataset or model weights were downloaded.

Observed outside the execution sandbox with `waldo-inspect`:

| Item | Observed value |
| --- | --- |
| OS / architecture | macOS 26.6.2 / arm64 (Apple Silicon) |
| Logical CPU count | 8 |
| Physical memory | 16 GiB |
| Python | 3.10.9 |
| PyTorch | 2.14.1 |
| TorchVision | 0.29.1 |
| Pillow | 12.3.0 |
| CUDA | Unavailable; no CUDA devices reported |
| Metal / MPS | Built and available |
| MPS tensor smoke check | Adding 1 to two ones returned `[2.0, 2.0]` |
| TorchVision CPU NMS smoke check | Passed; one input box returned index `[0]` |

The restricted sandbox reported MPS unavailable and could not query RAM.
The same inspection outside the sandbox confirmed MPS availability and 16 GiB.
Run `waldo-inspect` from your own terminal to check the environment in use.

MPS is PyTorch's backend for supported Apple GPUs; see the
[official MPS notes](https://docs.pytorch.org/docs/stable/notes/mps.html).
This check establishes that a tiny tensor operation works. It does not establish
that every detection operator works on MPS, that a full scene fits in memory,
or that a detector trains at a useful speed. CPU is available for this milestone.

Verification: 22 software tests passed, including dataset target shapes,
negative-image handling, invalid boxes and paths, duplicate records, corrupt
images, EXIF orientation, and the preview CLI. `pip check` reported no broken
requirements. Test images and coordinates were temporary geometric fixtures,
not Waldo examples or annotations. No model training or evaluation was run.
