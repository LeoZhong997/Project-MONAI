
from importlib import import_module


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
        tb = import_exception.__traceback__
        exception_str = f"{import_exception}"
        return tb, False
    else:   # found the module
        return the_module, True


def get_package_version(dep_name, default="NOT INSTALL or UNKNOWN VERSION."):
    """
    Try to load package and get version. If not found, return `default`.
    """
    dep, has_dep = optional_import(dep_name)
    if has_dep and hasattr(dep, "__version__"):
        return dep.__version__
    return default