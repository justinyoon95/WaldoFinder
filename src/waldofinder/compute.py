"""Report compute availability without loading a detector or training."""

import json
import os
import platform
import subprocess


def inspect_compute():
    report = {"python": platform.python_version(), "platform": platform.platform(),
              "architecture": platform.machine(), "logical_cpus": os.cpu_count()}
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True)
            report["memory_gib"] = round(int(result.stdout) / 1024**3, 2)
        except (OSError, ValueError, subprocess.CalledProcessError):
            report["memory_gib"] = "unavailable (OS/sandbox restriction)"
    try:
        import torch
        report.update(torch=torch.__version__, cuda_available=torch.cuda.is_available(),
                      mps_built=torch.backends.mps.is_built(), mps_available=torch.backends.mps.is_available())
        report["cuda_devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        device = "cuda" if report["cuda_available"] else "mps" if report["mps_available"] else "cpu"
        report["preferred_device"] = device
        try:
            report["tensor_smoke_test"] = (torch.ones(2, device=device) + 1).cpu().tolist()
        except RuntimeError as exc:
            report["tensor_smoke_test_error"] = str(exc)
        try:
            import torchvision
            from torchvision.ops import nms
            report["torchvision"] = torchvision.__version__
            report["torchvision_cpu_nms"] = nms(torch.tensor([[0., 0., 2., 2.]]), torch.tensor([1.]), 0.5).tolist()
        except (ImportError, RuntimeError, OSError) as exc:
            report["torchvision_error"] = str(exc)
    except (ImportError, OSError) as exc:
        report["torch_error"] = str(exc)
    return report


def main():
    print(json.dumps(inspect_compute(), indent=2))
