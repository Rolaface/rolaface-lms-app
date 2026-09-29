"""
Builds an OpenAPI 3 spec from whitelisted functions, so API docs follow the code.

Each endpoint's docstring holds a one-line title, then "---", then OpenAPI operation YAML
(tags, summary, description, parameters, requestBody, responses). The builder adds what the
code already says: the path, the allowed HTTP methods, the response envelope and Bearer auth.
"""

import importlib
import inspect
import pkgutil
from typing import Any, Dict, List, Optional

import frappe
import yaml

WRITE_METHODS = {"POST", "PUT", "PATCH"}
PARAMETER_KEYS = {"name", "in", "description", "required", "deprecated", "allowEmptyValue", "schema", "example", "examples", "style", "explode"}

COMPONENTS = {
	"securitySchemes": {
		"bearerAuth": {
			"type": "http",
			"scheme": "bearer",
			"description": "A session ID (sid), sent as Authorization: Bearer <sid>.",
		}
	},
	"schemas": {
		"Response": {
			"type": "object",
			"description": "Single-record responses are wrapped in message.",
			"properties": {
				"message": {
					"type": "object",
					"properties": {
						"status_code": {"type": "integer", "example": 200},
						"status": {"type": "string", "example": "success"},
						"message": {"type": "string"},
						"data": {"description": "The record or result."},
					},
				}
			},
		},
		"ListResponse": {
			"type": "object",
			"description": "List responses are not wrapped. pagination is only present on paginated lists.",
			"properties": {
				"status_code": {"type": "integer", "example": 200},
				"status": {"type": "string", "example": "success"},
				"message": {"type": "string"},
				"data": {"type": "array", "items": {"type": "object"}},
				"pagination": {"$ref": "#/components/schemas/Pagination"},
			},
		},
		"Pagination": {
			"type": "object",
			"properties": {
				"page": {"type": "integer"},
				"page_size": {"type": "integer"},
				"total": {"type": "integer"},
				"total_pages": {"type": "integer"},
				"has_next": {"type": "boolean"},
				"has_prev": {"type": "boolean"},
			},
		},
		"Error": {
			"type": "object",
			"properties": {
				"message": {
					"type": "object",
					"properties": {
						"status_code": {"type": "integer", "example": 400},
						"status": {"type": "string", "example": "fail"},
						"message": {"type": "string", "example": "Channel Name is required."},
						"data": {"nullable": True, "example": None},
					},
				}
			},
		},
		"FrappeError": {
			"type": "object",
			"description": "Raised by Frappe itself before the endpoint runs, e.g. no login or wrong HTTP method.",
			"properties": {"exc_type": {"type": "string"}, "exception": {"type": "string"}},
		},
	},
}

ERROR_RESPONSES = {
	"400": ("Invalid input.", "Error"),
	"401": ("Not logged in or the session expired.", "FrappeError"),
	"403": ("Not permitted, or the HTTP method is not allowed.", "FrappeError"),
	"404": ("Record not found.", "Error"),
	"409": ("Duplicate.", "Error"),
	"500": ("Unexpected server error.", "Error"),
}


def build_spec(packages: List[str], title: str, version: str, description: str = "", tag_order: Optional[List[str]] = None) -> Dict[str, Any]:
	paths, problems = {}, []
	for module in _api_modules(packages):
		for fn in _whitelisted_functions(module):
			path = f"/api/method/{module.__name__}.{fn.__name__}"
			paths[path] = _path_item(fn, path, problems)

	tags = sorted({tag for item in paths.values() for op in item.values() for tag in op.get("tags", [])})
	if tag_order:
		tags.sort(key=lambda t: tag_order.index(t) if t in tag_order else len(tag_order))

	info = {"title": title, "version": version, "description": description}
	if problems:
		info["description"] += "\n\n**Docstring problems:**\n" + "\n".join(f"- {p}" for p in problems)

	return {
		"openapi": "3.0.3",
		"info": info,
		"servers": [{"url": frappe.utils.get_url()}],
		"security": [{"bearerAuth": []}],
		"tags": [{"name": tag} for tag in tags],
		"paths": dict(sorted(paths.items())),
		"components": COMPONENTS,
		"x-docstring-problems": problems,
	}


def _api_modules(packages: List[str]):
	for package_name in packages:
		package = importlib.import_module(package_name)
		for info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
			if info.name.endswith(".api"):
				yield importlib.import_module(info.name)


def _whitelisted_functions(module):
	for _, fn in inspect.getmembers(module, inspect.isfunction):
		if fn.__module__ == module.__name__ and fn in frappe.whitelisted:
			yield fn


def _path_item(fn, path: str, problems: List[str]) -> Dict[str, Any]:
	title, doc, error = _parse_docstring(fn)
	if error:
		problems.append(f"`{path}`: {error}")

	methods = frappe.allowed_http_methods_for_whitelisted_func.get(fn) or ["GET", "POST", "PUT", "DELETE"]
	is_list = "send_response_list(" in inspect.getsource(fn)
	item = {}
	for method in methods:
		operation = {
			"operationId": f"{fn.__module__.split('.')[-2]}_{fn.__name__}_{method.lower()}",
			"tags": doc.get("tags") or [fn.__module__.split(".")[-2]],
			"summary": doc.get("summary") or title,
			"description": _description(title, doc),
			"parameters": _parameters(doc.get("parameters"), path, problems),
			"responses": _responses(doc.get("responses"), is_list),
		}
		if method in WRITE_METHODS and doc.get("requestBody"):
			operation["requestBody"] = doc["requestBody"]
		if fn in frappe.guest_methods:
			operation["security"] = [{}]
		if not operation["parameters"]:
			del operation["parameters"]
		item[method.lower()] = operation
	return item


def _parse_docstring(fn):
	doc = inspect.getdoc(fn) or ""
	title, _, yaml_part = doc.partition("---")
	title = title.strip().splitlines()[0] if title.strip() else fn.__name__.replace("_", " ").capitalize()
	if not yaml_part.strip():
		return title, {}, "no OpenAPI YAML after '---'"
	try:
		parsed = yaml.safe_load(yaml_part) or {}
	except yaml.YAMLError as e:
		return title, {}, f"YAML error: {str(e).splitlines()[0]}"
	if not isinstance(parsed, dict):
		return title, {}, "OpenAPI YAML is not a mapping"
	split = _split_keys(parsed)
	if split:
		return title, parsed, f"text split at a comma inside {{...}}, quote it: {split[:3]}"
	return title, parsed, None


def _split_keys(node) -> List[str]:
	"""Keys like 'or a temporary one' with no value: an unquoted comma inside YAML's {...} form."""
	found = []
	if isinstance(node, dict):
		for key, value in node.items():
			if value is None and isinstance(key, str) and " " in key:
				found.append(key)
			found.extend(_split_keys(value))
	elif isinstance(node, list):
		for value in node:
			found.extend(_split_keys(value))
	return found


def _description(title: str, doc: Dict[str, Any]) -> str:
	description = doc.get("description") or ""
	if doc.get("summary") and doc.get("summary") != title:
		description = f"**{title}**\n\n{description}".strip()
	return description


def _parameters(parameters, path: str, problems: List[str]) -> List[Dict[str, Any]]:
	result = []
	for param in parameters or []:
		if not isinstance(param, dict) or not param.get("name") or not param.get("in"):
			problems.append(f"`{path}`: a parameter is missing name or in")
			continue
		unknown = set(param) - PARAMETER_KEYS
		if unknown:
			problems.append(f"`{path}`: parameter '{param['name']}' has unexpected keys {sorted(map(str, unknown))} (quote descriptions with commas)")
			param = {k: v for k, v in param.items() if k in PARAMETER_KEYS}
		param.setdefault("schema", {"type": "string"})
		result.append(param)
	return result


def _responses(documented, is_list: bool) -> Dict[str, Any]:
	schema_ref = {"$ref": f"#/components/schemas/{'ListResponse' if is_list else 'Response'}"}
	responses = {}
	for code, value in (documented or {}).items():
		value = value if isinstance(value, dict) else {"description": str(value)}
		value.setdefault("description", "")
		if str(code).startswith("2"):
			value.setdefault("content", {"application/json": {"schema": schema_ref}})
		elif str(code) in ERROR_RESPONSES:
			value.setdefault("content", {"application/json": {"schema": {"$ref": f"#/components/schemas/{ERROR_RESPONSES[str(code)][1]}"}}})
		responses[str(code)] = value

	if not any(code.startswith("2") for code in responses):
		responses["200"] = {"description": "Success.", "content": {"application/json": {"schema": schema_ref}}}
	for code, (text, schema) in ERROR_RESPONSES.items():
		responses.setdefault(code, {"description": text, "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema}"}}}})
	return dict(sorted(responses.items()))
