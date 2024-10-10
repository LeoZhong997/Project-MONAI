import sys
import tempfile
import os
import logging
from pathlib import Path
from typing import Any

from BaseProjects.config.type_definitions import PathLike

DEFAULT_FMT = "%(asctime)s - %(levelname)s - %(message)s"

def get_logger(
    module_name: str = "default.apps",
    fmt: str = DEFAULT_FMT,
    datefmt: str | None = None,
    logger_handler: logging.Handler | None = None,
) -> logging.Logger:
    """
    Get a `module_name` logger with the specified format and date format.
    By default, the logger will print to `stdout` at the INFO level.
    If `module_name` is `None`, return the root logger.
    `fmt` and `datafmt` are passed to a `logging.Formatter` object
    (https://docs.python.org/3/library/logging.html#formatter-objects).
    `logger_handler` can be used to add an additional handler.
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


def check_hash(filepath: PathLike, val: str | None = None, hash_type: str = "md5"):
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


def download_url(
    url: str,
    filepath: PathLike = "",
    hash_val: str | None = None,
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


def extractall(
    filepath: PathLike,
    output_dir: PathLike = ".",
    hash_val: str | None = None,
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
    pass


def download_and_extract(
    url: str,
    filepath: PathLike = "",
    output_dir: PathLike = ".",
    hash_val: str | None = None,
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


if __name__ == "__main__":
    download_and_extract(

    )