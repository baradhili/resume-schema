#!/usr/bin/env python3

# pyright: reportAny=false
# pyright: reportExplicitAny=false
# pyright: reportUnknownVariableType=false

from typing import Any
import json
import os
import sys

def merge_schemas(types_file: str, schema_file: str) -> dict[str, Any]:
	"""Merge types.json definitions into schema.json, including only used refs."""

	# Load files
	with open(types_file) as f:
		types_schema: dict[str, Any] = json.load(f)

	with open(schema_file) as f:
		schema: dict[str, Any] = json.load(f)

	types_filename: str = os.path.basename(types_file)

	# Extract ALL definitions from types
	all_defs: dict[str, Any] = types_schema.get("definitions", {})

	# Find ALL $ref values used in schema
	used_refs: set[str] = set()

	def collect_refs(obj: Any) -> None:
		if isinstance(obj, dict):
			if "$ref" in obj:
				ref_val = obj["$ref"]
				if isinstance(ref_val, str):
					if ref_val.startswith(f"{types_filename}#/definitions/"):
						def_name: str = ref_val[len(f"{types_filename}#/definitions/"):]
						used_refs.add(def_name)

			for value in obj.values():
				collect_refs(value)

		elif isinstance(obj, list):
			for item in obj:
				collect_refs(item)

	collect_refs(schema)

	# Filter definitions - ONLY include used ones
	used_defs: dict[str, Any] = {
		name: all_defs[name] for name in used_refs if name in all_defs
	}

	# Merge ONLY used definitions into schema
	if "definitions" in schema:
		del schema["definitions"]  # type: ignore

	schema["definitions"] = used_defs  # type: ignore

	# Fix all external refs to internal refs
	def fix_refs(obj: Any) -> Any:
		if isinstance(obj, dict):
			if "$ref" in obj:
				ref_val = obj["$ref"]
				if isinstance(ref_val, str):
					if ref_val.startswith(f"{types_filename}#/definitions/"):
						obj["$ref"] = "#/definitions/" + ref_val[len(f"{types_filename}#/definitions/"):]  # type: ignore
			for key, value in obj.items():
				obj[key] = fix_refs(value)  # type: ignore
			return obj

		elif isinstance(obj, list):
			return [fix_refs(item) for item in obj]

		return obj

	fix_refs(schema)
	return schema


## Main
if __name__ == "__main__":
	USE_TABS = True

	# Perform argparsing
	if len(sys.argv) < 3:
		print(f"Usage: {sys.argv[0]} TYPES.json SCHEMA.json", file=sys.stderr)
		sys.exit(1)

	# Merge and output
	schema = merge_schemas(sys.argv[1], sys.argv[2])
	jsons = json.dumps(schema, indent=4)

	if USE_TABS:
		print(jsons.replace(" " * 4, "\t"))
	else:
		print(jsons)
