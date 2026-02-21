#!/usr/bin/env python3

# pyright: reportAny=false
# pyright: reportExplicitAny=false
# pyright: reportUnknownVariableType=false

from dataclasses import dataclass
from typing import Any
import json
import os
import sys
import argparse

__DEFS_KEYNAME_OLD = "definitions"
__DEFS_KEYNAME_NEW = "$defs"

@dataclass
class Options:
	"""Configuration options for schema merging."""
	use_tabs: bool = True
	force_defs_syntax: bool = False

def merge_schemas(types_file: str, schema_file: str, force_defs_syntax: bool) -> dict[str, Any]:
	"""Merge types.json definitions into schema.json, including only used refs."""

	# Load files
	with open(types_file) as f:
		types_schema: dict[str, Any] = json.load(f)

	with open(schema_file) as f:
		schema: dict[str, Any] = json.load(f)

	types_filename: str = os.path.basename(types_file)

	# Get the schema versions between both files and ensure they line up
	types_schema_ver = str(types_schema.get("$schema", ""))
	schema_ver = str(schema.get("$schema", ""))
	if types_schema_ver != schema_ver:
		print(f"Error: Schema version mismatch between '{schema_file}' and '{types_file}'", file=sys.stderr)
		exit(1)

	# Pick the correct key name for definitions (draft-2020-12 uses `$defs` instead of `definitions`)
	def_keyname = __DEFS_KEYNAME_OLD
	def_out_keyname = __DEFS_KEYNAME_OLD
	if "draft/2020-12/schema" in types_schema_ver:
		def_keyname = __DEFS_KEYNAME_NEW
		def_out_keyname = __DEFS_KEYNAME_NEW

	# If forcing the use of $defs, set the out keyname accordingly
	if force_defs_syntax:
		def_out_keyname = __DEFS_KEYNAME_NEW

	# Extract ALL definitions from types
	all_defs: dict[str, Any] = types_schema.get(def_keyname, {})

	# Find ALL $ref values used in schema
	used_refs: set[str] = set()

	def collect_refs(obj: Any) -> None:
		if isinstance(obj, dict):
			if "$ref" in obj:
				ref_val = obj["$ref"]
				if isinstance(ref_val, str):
					if ref_val.startswith(f"{types_filename}#/{def_keyname}/"):
						def_name: str = ref_val[len(f"{types_filename}#/{def_keyname}/"):]
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
	if def_keyname in schema:
		del schema[def_keyname]

	schema[def_out_keyname] = used_defs

	# Fix all external refs to internal refs
	def fix_refs(obj: Any) -> Any:
		if isinstance(obj, dict):
			if "$ref" in obj:
				ref_val = obj["$ref"]
				if isinstance(ref_val, str):
					if ref_val.startswith(f"{types_filename}#/{def_keyname}/"):
						obj["$ref"] = f"#/{def_out_keyname}/" + ref_val[len(f"{types_filename}#/{def_keyname}/"):]
			for key, value in obj.items():
				obj[key] = fix_refs(value)
			return obj

		elif isinstance(obj, list):
			return [fix_refs(item) for item in obj]

		return obj

	fix_refs(schema)

	# If forcing the use of $defs, correct the version identifier to match; basic replacement, might be better to use patterns instead
	if force_defs_syntax:
		schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"

	return schema


## Main
if __name__ == "__main__":
	# Setup default options
	opts = Options()

	# Setup argument parser with both positional arguments and optional flags
	parser = argparse.ArgumentParser(
		description="Merge types.json definitions into schema.json, including only used refs."
	)

	# Add positional arguments (required)
	parser.add_argument("types_file", help="Path to the TYPES.json file")
	parser.add_argument("schema_file", help="Path to the SCHEMA.json file")

	# Add optional flag for tab indentation
	parser.add_argument(
		"--use-tabs",
		action="store_true",
		help="Use tabs instead of spaces for indentation in output"
	)

	# Add optional flag for forcing $defs syntax for $refs
	parser.add_argument(
		"--force-defs-syntax",
		action="store_true",
		help="Force the usage of `$defs` over the old `definitions` syntax"
	)

	# Parse arguments
	args = parser.parse_args()

	# Override defaults with command line arguments if provided
	opts.use_tabs = args.use_tabs or opts.use_tabs
	opts.force_defs_syntax = args.force_defs_syntax or opts.force_defs_syntax

	# Merge the schemas
	schema = merge_schemas(args.types_file, args.schema_file, opts.force_defs_syntax)
	jsons = json.dumps(schema, indent=4)

	# Apply options
	if opts.use_tabs:
		jsons = jsons.replace(" " * 4, "\t")

	print(jsons)
