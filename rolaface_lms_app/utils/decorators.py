import importlib
from functools import wraps
import frappe

_validator_cache = {}

def validate_payload(validator_name=None):
    def decorator(func):
        module_path = func.__module__
        base_path = module_path.rsplit(".", 1)[0]
        validator_module_path = f"{base_path}.validate"
        validator_fn_name = validator_name or f"validate_{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            validate_fn = _get_validate_fn(validator_module_path, validator_fn_name)
            if validate_fn:
                payload = {**frappe.local.form_dict, **kwargs}
                validate_fn(payload)
            return func(*args, **kwargs)

        return wrapper
    return decorator


def _get_validate_fn(validator_module_path, validator_fn_name):
    cache_key = f"{validator_module_path}.{validator_fn_name}"
    if cache_key in _validator_cache:
        return _validator_cache[cache_key]

    validate_fn = None
    try:
        validator_module = importlib.import_module(validator_module_path)
        validate_fn = getattr(validator_module, validator_fn_name, None)
    except ModuleNotFoundError:
        pass

    _validator_cache[cache_key] = validate_fn
    return validate_fn