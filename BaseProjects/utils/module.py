
import enum
from importlib import import_module
from collections.abc import Collection, Hashable, Mapping
from typing import Any, Union


def look_up_option(
    opt_str: Hashable,
    supported: Union[Collection, enum.EnumMeta],
    default: Any = "no_default",
    print_all_options: bool = True,
) -> Any:
    """
    Look up the option in the supported collection and return the matched item.
    Raise a value error possibly with a guess of the closest match.

    Args:
        opt_str: The option string or Enum to look up.
        supported: The collection of supported options, it can be list, tuple, set, dict, or Enum.
        default: If it is given, this method will return `default` when `opt_str` is not found,
            instead of raising a `ValueError`. Otherwise, it defaults to `"no_default"`,
            so that the method may raise a `ValueError`.
        print_all_options: whether to print all available options when `opt_str` is not found. Defaults to True

    Examples:

    .. code-block:: python

        from enum import Enum
        from monai.utils import look_up_option
        class Color(Enum):
            RED = "red"
            BLUE = "blue"
        look_up_option("red", Color)  # <Color.RED: 'red'>
        look_up_option(Color.RED, Color)  # <Color.RED: 'red'>
        look_up_option("read", Color)
        # ValueError: By 'read', did you mean 'red'?
        # 'read' is not a valid option.
        # Available options are {'blue', 'red'}.
        look_up_option("red", {"red", "blue"})  # "red"

    Adapted from https://github.com/NifTK/NiftyNet/blob/v0.6.0/niftynet/utilities/util_common.py#L249
    """

    if not isinstance(opt_str, Hashable):
        raise ValueError(f"Unrecognized option type: {type(opt_str)}: {opt_str}.")
    if isinstance(opt_str, str):
        opt_str = opt_str.strip()
    if isinstance(supported, enum.EnumMeta):
        if isinstance(opt_str, str) and opt_str in {item.value for item in supported}:
            return supported(opt_str)   # such as: "example" in MyEnum
        if isinstance(opt_str, enum.Enum) and opt_str in supported:
            return opt_str              # such as: MyEnum.EXAMPLE in MyEnum
    elif isinstance(supported, Mapping) and opt_str in supported:
        return supported[opt_str]       # such as: MyDict[key]
    elif isinstance(supported, Collection) and opt_str in supported:
        return opt_str
    
    if default != "no_default":
        return default
    
    set_to_check: set
    if isinstance(supported, enum.EnumMeta):
        set_to_check = {item.value for item in supported}
    else:
        set_to_check = set(supported) if supported is not None else set()
    if not set_to_check:
        raise ValueError(f"No options available: {supported}")
    support_msg = f"Available options are {set_to_check}" if print_all_options else ""
    raise ValueError(f"Unsupported option '{opt_str}', " + support_msg)


def min_version(the_module: Any, min_version_str: str = ""):
    """
    Convert version strings into tuples of int and compare them.

    Returns True if the module's version is greater or equal to the 'min_version'.
    When min_version_str is not provided, it always returns True.
    """
    if not min_version_str or not hasattr(the_module, "__version__"):
        return True
    
    mod_version = tuple(int(x) for x in the_module.__version__.split(".")[:2])
    required = tuple(int(x) for x in min_version_str.split(".")[:2])
    return mod_version >= required



def optional_import(
        module: str, 
        version: str = "",
        name: str = ""
):
    """
    Imports an optional module specified by `module` string.
    """
    try:
        pkg = __import__(module)
        the_module = import_module(module)
        is_namespace = getattr(the_module, "__file__", None) is None and hasattr(the_module, "__path__")
        if is_namespace:
            raise AssertionError
        if name:
            the_module = getattr(the_module, name)
    except Exception as import_exception:   # any exception during import
        # tb = import_exception.__traceback__
        # exception_str = f"{import_exception}"
        return None, False
    else:   # found the module
        if min_version(the_module, version):
            return the_module, True
        else:
            return None, False


def get_package_version(dep_name, default="NOT INSTALL or UNKNOWN VERSION."):
    """
    Try to load package and get version. If not found, return `default`.
    """
    dep, has_dep = optional_import(dep_name)
    if has_dep and hasattr(dep, "__version__"):
        return dep.__version__
    return default