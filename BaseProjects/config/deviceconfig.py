import getpass
import platform
import sys
import monai
import numpy as np
import torch
import re
import os

from typing import OrderedDict, TextIO

import torch.version

from BaseProjects.utils.module import get_package_version, optional_import

psutil, has_psutil = optional_import("psutil")
psutil_version = psutil.__version__ if has_psutil else "NOT INSTALLED or UNKNOWN VERSION."


def get_config_values():
    output = OrderedDict()

    output["MONAI"] = monai.__version__
    output["Numpy"] = np.version.full_version
    output["Pytorch"] = torch.__version__

    return output


def get_optional_config_values():
    output = OrderedDict()
    package_name_dict = {
        "ITK": "itk",
        "Nibabel": "nibabel",
        "scikit-image": "skimage",
        "Pillow": "PIL",
        "Tensorboard": "tensorboard",
        "gdown": "gdown",
        "TorchVision": "torchvision",
        "tqdm": "tqdm",
        "lmdb": "lmdb",
    }

    for name, package_name in package_name_dict.items():
        output[name] = get_package_version(package_name)

    return output


def print_config(file=sys.stdout):
    for k, v in get_config_values().items():
        print(f"{k} version: {v}", file=file, flush=True)

    username = getpass.getuser()
    print(f"\nusername: {username}", file=file, flush=True)

    print("\nOptional dependencies:", file=file, flush=True)
    for k, v in get_optional_config_values().items():
        print(f"{k} version: {v}", file=file, flush=True)


def _dict_append(in_dict, key, fn):
    try:
        in_dict[key] = fn() if callable(fn) else fn
    except BaseException:
        in_dict[key] = "UNKNOWN for given OS"


def get_system_info():
    output = OrderedDict()

    _dict_append(output, "System", platform.system)
    if output["System"] == "Windows":
        _dict_append(output, "Win32 version", platform.win32_ver)
        if hasattr(platform, "win32_edition"):
            _dict_append(output, "Win32 edition", platform.win32_edition)
    elif output["System"] == "Darwin":
        _dict_append(output, "Mac version", lambda: platform.mac_ver()[0])
    else:
        with open("/etc/os-release") as rel_f:
            linux_ver = re.search(r'PRETTY_NAME="(.*)"', rel_f.read())
        if linux_ver:
            _dict_append(output, "Linux version", lambda: linux_ver.group(1))
    
    _dict_append(output, "Plaform", platform.platform)
    _dict_append(output, "Processor", platform.processor)
    _dict_append(output, "Machine", platform.machine)
    _dict_append(output, "Python version", platform.python_version)

    if not has_psutil:
        _dict_append(output, "`psutil` missing", lambda: "run `pip install psutil`")
    else:
        p = psutil.Process()
        with p.oneshot():
            _dict_append(output, "Process name", p.name)
            _dict_append(output, "Command", p.cmdline)
            _dict_append(output, "Open files", p.open_files)
            _dict_append(output, "Num physical CPUs", lambda: psutil.cpu_count(logical=False))
            _dict_append(output, "Num logical CPUs", lambda: psutil.cpu_count(logical=True))
            _dict_append(output, "Num usable CPUs", lambda: len(psutil.Process().cpu_affinity()))
            _dict_append(output, "CPU usage (%)", lambda: psutil.cpu_percent(percpu=True))
            _dict_append(output, "CPU freq. (MHz)", lambda: round(psutil.cpu_freq(percpu=False)[0]))
            _dict_append(
                output,
                "Load avg. in last 1, 5, 15 mins (%)",
                lambda: [round(x / psutil.cpu_count() * 100, 1) for x in psutil.getloadavg()],
            )
            _dict_append(output, "Disk usage (%)", lambda: psutil.disk_usage(os.getcwd()).percent)
            _dict_append(
                output,
                "Avg. sensor temp. (Celsius)",
                lambda: np.round(
                    np.mean([item.current for sublist in psutil.sensors_temperatures().values() for item in sublist]), 1
                ),
            )
            mem = psutil.virtual_memory()
            _dict_append(output, "Total physical memory (GB)", lambda: round(mem.total / 1024**3, 1))
            _dict_append(output, "Available memory (GB)", lambda: round(mem.available / 1024**3, 1))
            _dict_append(output, "Used memory (GB)", lambda: round(mem.used / 1024**3, 1))

    return output


def print_system_info(file=sys.stdout):
    for k, v in get_system_info().items():
        print(f"{k}: {v}", file=file, flush=True)

    
def get_gpu_info():
    output = OrderedDict()

    num_gpus = torch.cuda.device_count()
    _dict_append(output, "Num GPUs", lambda: num_gpus)

    _dict_append(output, "Has CUDA", lambda: bool(torch.cuda.is_available()))
    if output["Has CUDA"]:
        _dict_append(output, "CUDA version", lambda: torch.version.cuda)
    cudnn_ver = torch.backends.cudnn.version()
    _dict_append(output, "cuDNN enabled", lambda: bool(cudnn_ver))
    _dict_append(output, "NVIDIA_TF32_OVERRIED", os.environ.get("NVIDIA_TF32_OVERRIDE"))
    _dict_append(output, "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE", os.environ.get("TORCH_ALLOW_TF32_CUBLAS_OVERRIDE"))

    if cudnn_ver:
        _dict_append(output, "cuDNN version", lambda: cudnn_ver)

    if num_gpus > 0:
        _dict_append(output, "Current device", torch.cuda.current_device)
        _dict_append(output, "Library compiled for CUDA architectures", torch.cuda.get_arch_list)

    for gpu in range(num_gpus):
        gpu_info = torch.cuda.get_device_properties(gpu)
        _dict_append(output, f"GPU {gpu} Name", gpu_info.name)
        _dict_append(output, f"GPU {gpu} Is integrated", gpu_info.is_integrated)
        _dict_append(output, f"GPU {gpu} Is multi GPU board", bool(gpu_info.is_multi_gpu_board))
        _dict_append(output, f"GPU {gpu} Multi processor count", gpu_info.multi_processor_count)
        _dict_append(output, f"GPU {gpu} Total memory (GB)", round(gpu_info.total_memory / 1024**3, 1))
        _dict_append(output, f"GPU {gpu} CUDA capability (maj.min)", f"{gpu_info.major}.{gpu_info.minor}")

    return output

def print_gpu_info(file=sys.stdout):
    for k, v in get_gpu_info().items():
        print(f"{k}: {v}", file=file, flush=True)


def print_debug_info(file: TextIO = sys.stdout):
    print("================================", file=file, flush=True)
    print("Printing MONAI config...", file=file, flush=True)
    print("================================", file=file, flush=True)
    print_config(file)
    print("\n================================", file=file, flush=True)
    print("Printing system config...")
    print("================================", file=file, flush=True)
    print_system_info(file)
    print("\n================================", file=file, flush=True)
    print("Printing GPU config...")
    print("================================", file=file, flush=True)
    print_gpu_info(file)


if __name__ == "__main__":
    print_debug_info()
