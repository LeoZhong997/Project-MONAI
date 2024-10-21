import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import os
import logging
from pathlib import Path
from typing import Any, Union
from urllib.error import URLError, ContentTooShortError, HTTPError
from urllib.parse import urlparse
from urllib.request import urlopen, urlretrieve
import zipfile

from BaseProjects.config.type_definitions import PathLike
from BaseProjects.utils.module import look_up_option, optional_import

gdown, has_gdown = optional_import("gdown", "4.7.3")

DEFAULT_FMT = "%(asctime)s - %(levelname)s - %(message)s"
SUPPORTED_HASH_TYPES = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}


def get_logger(
        module_name: str = "default.apps",
        fmt: str = DEFAULT_FMT,
        datefmt: Union[str, None] = None,
        logger_handler: Union[logging.Handler, None] = None,
) -> logging.Logger:
    """
    Get a `module_name` logger with the specified format and date format.

    By default, the logger will print to `stdout` at the INFO level.
    If `module_name` is `None`, return the root logger.

    Parameters:
    module_name (str): The name of the module to associate with the logger.
        Default is "default.apps".
    fmt (str): The format string for the logger messages.
        Default is DEFAULT_FMT.
    datefmt (str or None): The date format string for the logger messages.
        Default is None.
    logger_handler (logging.Handler or None): An additional handler to add to the logger.
        Default is None.

    Returns:
    logging.Logger: The configured logger.

    """
    adds_stdout_handler = module_name is not None and module_name not in logging.root.manager.loggerDict
    logger = logging.getLogger(module_name)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if adds_stdout_handler:  # don't add multiple stdout or add to the root
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if logger_handler is not None:
        logger.addHandler(logger_handler)
    return logger


logger = get_logger("default.apps")


def _basename(p: PathLike):
    """
    get the last part of the path (removing the trailing slash if it exists)
    """
    # os.path.sep = path separator, os.path.altsep = root dir
    sep = os.path.sep + (os.path.altsep or "") + "/ "
    # Path.name = base name of path
    return Path(f"{p}".rstrip(sep)).name


def check_hash(filepath: PathLike, val: Union[str, None] = None, hash_type: str = "md5"):
    """
    Verify hash signature of specified file.

    Args:
        filepath: path of source file to verify hash value.
        val: expected hash value of the file.
        hash_type: type of hash algorithm to use, default is `"md5"`.
            The supported hash types are `"md5"`, `"sha1"`, `"sha256"`, `"sha512"`.
            See also: :py:data:`monai.apps.utils.SUPPORTED_HASH_TYPES`.
    """
    if val is None:
        logger.info(f"Excepted {hash_type} is None, skip {hash_type} check for file {filepath}.")
        return True
    actual_hash_func = look_up_option(hash_type, SUPPORTED_HASH_TYPES)

    if sys.version_info > (3, 9):
        actual_hash = actual_hash_func(usedforsecurity=False)
    else:
        actual_hash = actual_hash_func()

    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                actual_hash.update(chunk)
    except Exception as e:
        logger.error("Exception in check_hash: {e}")
        return False
    if val != actual_hash.hexdigest():
        logger.error(f"check_hash failed {actual_hash.hexdigest()}.")
        return False

    logger.info(f"Verified '{_basename(filepath)}', {hash_type}: {val}.")
    return True


def _download_with_progress(url: str, filepath: Path, progress: bool = True):
    """
    Retrieve file from `url` to `filepath`, optionally showing a progress bar.
    """
    try:
        urlretrieve(url, filepath)
    except (URLError, ContentTooShortError, HTTPError) as e:
        logger.error(f"Download failed from {url} to {filepath}.")
        raise e


def download_url(
        url: str,
        filepath: PathLike = "",
        hash_val: Union[str, None] = None,
        hash_type: str = "md5",
        progress: bool = True,
        **gdown_kwargs: Any,
):
    """
    Download file from specified URL link, support process bar and hash check.

    Args:
        url: source URL link to download file.
        filepath: target filepath to save the downloaded file (including the filename).
            If undefined, `os.path.basename(url)` will be used.
        hash_val: expected hash value to validate the downloaded file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.
        progress: whether to display a progress bar.
        gdown_kwargs: other args for `gdown` except for the `url`, `output` and `quiet`.
            these args will only be used if download from google drive.
            details of the args of it:
            https://github.com/wkentaro/gdown/blob/main/gdown/download.py

    Raises:
        RuntimeError: When the hash validation of the ``filepath`` existing file fails.
        RuntimeError: When a network issue or denied permission prevents the
            file download from ``url`` to ``filepath``.
        URLError: See urllib.request.urlretrieve.
        HTTPError: See urllib.request.urlretrieve.
        ContentTooShortError: See urllib.request.urlretrieve.
        IOError: See urllib.request.urlretrieve.
        RuntimeError: When the hash validation of the ``url`` downloaded file fails.

    """
    if not filepath:
        # Path.resolve() -> absolute path
        filepath = Path(".", _basename(url)).resolve()
        logger.info(f"Default downloading to '{filepath}'")
    filepath = Path(filepath)
    if filepath.exists():
        if not check_hash(filepath, hash_val, hash_type):
            raise RuntimeError(
                f"{hash_type} check of existing file failed: filepath={filepath}, excepted {hash_type}={hash_val}"
            )
        logger.info(f"File exists: {filepath}, skipped downloading.")
        return
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_name = Path(tmp_dir, _basename(filepath))
            if urlparse(url).netloc == "drive.google.com":
                if not has_gdown:
                    raise RuntimeError("To download files from Google Drive, please install the gdown dependency.")
                if "fuzzy" not in gdown_kwargs:
                    gdown_kwargs["fuzzy"] = True
                gdown.download(url, f"{tmp_name}", quite=not progress, **gdown_kwargs)
            elif urlparse(url).netloc == "cloud-api.yandex.net":
                with urlopen(url) as response:
                    code = response.getcode()
                    if code == 200:
                        _download_url = json.load(response)["href"]
                        _download_with_progress(_download_url, tmp_name, progress)
                    else:
                        raise RuntimeError(
                            f"Error code {code}, received from {url} "
                            + f"to {filepath} failed due to network issue or denied permission."
                        )
            else:
                _download_with_progress(url, tmp_name, progress)
            if not tmp_name.exists():
                raise RuntimeError(
                    f"Download of file from {url} to {filepath} failed due to network issue or denied permission.")
            filedir = filepath.parent
            if filedir:
                os.makedirs(filedir, exist_ok=True)
            shutil.move(f"{tmp_name}", f"{filepath}")
    except (PermissionError, NotADirectoryError):
        pass

    logger.info(f"Download: {filepath}")
    if not check_hash(filepath, hash_val, hash_type):
        raise RuntimeError(
            f"{hash_type} check of downloaded file failed: URL={url}."
        )


def extractall(
        filepath: PathLike,
        output_dir: PathLike = ".",
        hash_val: Union[str, None] = None,
        hash_type: str = "md5",
        file_type: str = "",
        has_base: bool = True,
):
    """
    Extract file to the output directory.
    Expected file types are: `zip`, `tar.gz` and `tar`.

    Args:
        filepath: the file path of compressed file.
        output_dir: target directory to save extracted files.
        hash_val: expected hash value to validate the compressed file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.
        file_type: string of file type for decompressing. Leave it empty to infer the type from the filepath basename.
        has_base: whether the extracted files have a base folder. This flag is used when checking if the existing
            folder is a result of `extractall`, if it is, the extraction is skipped. For example, if A.zip is unzipped
            to folder structure `A/*.png`, this flag should be True; if B.zip is unzipped to `*.png`, this flag should
            be False.

    Raises:
        RuntimeError: When the hash validation of the ``filepath`` compressed file fails.
        NotImplementedError: When the ``filepath`` file extension is not one of [zip", "tar.gz", "tar"].
    """

    if has_base:
        cache_dir = Path(output_dir, _basename(filepath).split(".")[0])
    else:
        cache_dir = Path(output_dir)
    if cache_dir.exists() and next(cache_dir.iterdir(), None) is not None:
        logger.info(f"Non-empty folder exists in {cache_dir}, skipped extracting.")
        return

    filepath = Path(filepath)
    if hash_val and not check_hash(filepath, hash_val, hash_type):
        raise RuntimeError(f"{hash_type} check of compressed file failed: "
                           f"filepath={filepath}, expected {hash_type}={hash_val}")
    logger.info(f"Writing into directory: {output_dir}")
    _file_type = file_type.lower().strip()
    if filepath.name.endswith("zip") or _file_type == "zip":
        zip_file = zipfile.ZipFile(filepath)
        zip_file.extractall(output_dir)
        zip_file.close()
        return
    if filepath.name.endswith("tar") or filepath.name.endswith("tar.gz") or "tar" in _file_type:
        tar_file = tarfile.open(filepath)
        tar_file.extractall(output_dir)
        tar_file.close()
        return
    raise NotImplementedError(
        f"Unsupported file type, available options are: ['zip', 'tar.gz', 'tar']. name={filepath}, type={file_type}."
    )


def download_and_extract(
        url: str,
        filepath: PathLike = "",
        output_dir: PathLike = ".",
        hash_val: Union[str, None] = None,
        hash_type: str = "md5",
        file_type: str = "",
        has_base: bool = True,
        progress: bool = True,
) -> None:
    """
    Download file from URL and extract it to the output directory.

    Args:
        url: source URL link to download file.
        filepath: the file path of the downloaded compressed file.
            use this option to keep the directly downloaded compressed file, to avoid further repeated downloads.
        output_dir: target directory to save extracted files.
            default is the current directory.
        hash_val: expected hash value to validate the downloaded file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.
        file_type: string of file type for decompressing. Leave it empty to infer the type from url's base file name.
        has_base: whether the extracted files have a base folder. This flag is used when checking if the existing
            folder is a result of `extractall`, if it is, the extraction is skipped. For example, if A.zip is unzipped
            to folder structure `A/*.png`, this flag should be True; if B.zip is unzipped to `*.png`, this flag should
            be False.
        progress: whether to display progress bar.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        filename = filepath or Path(tmp_dir, _basename(url)).resolve()
        download_url(url=url, filepath=filename, hash_val=hash_val, hash_type=hash_type, progress=progress)
        extractall(filepath=filename, output_dir=output_dir, file_type=file_type, has_base=has_base)


def get_hash_val(filepath, hash_type):
    actual_hash_func = look_up_option(hash_type, SUPPORTED_HASH_TYPES)

    if sys.version_info > (3, 9):
        actual_hash = actual_hash_func(usedforsecurity=False)
    else:
        actual_hash = actual_hash_func()

    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                actual_hash.update(chunk)
    except Exception as e:
        logger.error("Exception in check_hash: {e}")
        return False
    return actual_hash.hexdigest()


if __name__ == "__main__":
    root_dir = "/data/result/zhongzhiqiang/MONAI/debug/download_test"
    os.makedirs(root_dir, exist_ok=True)
    resource = "https://mirrors.tuna.tsinghua.edu.cn/github-release/git-for-windows/git/LatestRelease/MinGit-2.47.0-64-bit.zip"
    md5 = "e1312f449e17c9aac237e1ceeb50fad6"

    compressed_file = os.path.join(root_dir, "MinGit-2.47.0-64-bit.zip")
    # file_md5 = get_hash_val(compressed_file, "md5")
    # print(f"file_md5: {file_md5}")
    data_dir = os.path.join(root_dir, "MinGit")
    if not os.path.exists(data_dir):
        download_and_extract(resource, compressed_file, data_dir, md5)
