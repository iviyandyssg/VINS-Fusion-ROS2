#!/usr/bin/env python3
"""Generate a Squash TM import XLS from an empty official template and JSON.

Dependencies: xlrd xlwt xlutils. Creates classic cases and steps only.
"""

import argparse
import html
import json
from pathlib import Path

import xlrd
from xlutils.copy import copy as copy_workbook


def component(value):
    if not isinstance(value, str) or not value.strip() or any(
        char in value for char in "/\\"
    ):
        raise ValueError(f"Invalid path component: {value!r}")
    return value.strip()


def rich_text(value):
    return "<p>" + html.escape(str(value)).replace("\n", "<br/>") + "</p>"


def generate(template, cases_file, project, output):
    if template.suffix.lower() != ".xls" or output.suffix.lower() != ".xls":
        raise ValueError("Template and output must both be .xls files")
    if output.exists() or template.resolve() == output.resolve():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Input must be a nonempty JSON array")
    source = xlrd.open_workbook(str(template), formatting_info=True)
    required = {"TEST_CASES", "STEPS", "PARAMETERS", "DATASETS", "LINK_REQ_TC"}
    if not required.issubset(source.sheet_names()):
        raise ValueError("Template must contain the five official worksheets")
    for name in required:
        sheet = source.sheet_by_name(name)
        if any(str(value).strip() for row in range(1, sheet.nrows)
               for value in sheet.row_values(row)):
            raise ValueError(f"Use an empty template; {name} contains data")

    workbook = copy_workbook(source)
    headers = {}
    for name in ("TEST_CASES", "STEPS"):
        columns = source.sheet_by_name(name).row_values(0)
        headers[name] = {str(value).strip(): i for i, value in enumerate(columns)}

    rows = {"TEST_CASES": 1, "STEPS": 1}

    def append(name, values):
        missing = set(values) - headers[name].keys()
        if missing:
            raise ValueError(f"{name} missing columns: {sorted(missing)}")
        if rows[name] >= 65536:
            raise ValueError("XLS row limit exceeded; split the input")
        sheet = workbook.get_sheet(source.sheet_names().index(name))
        for field, value in values.items():
            if isinstance(value, str) and len(value) > 32767:
                raise ValueError(f"Cell too long: {field}")
            sheet.write(rows[name], headers[name][field], value)
        rows[name] += 1

    project = component(project)
    seen = set()
    for case in cases:
        folder = case.get("folder", "")
        folders = [component(part) for part in folder.split("/")] if folder else []
        path = "/" + "/".join([project, *folders, component(case["name"])])
        if path in seen:
            raise ValueError(f"Duplicate case path: {path}")
        seen.add(path)
        append("TEST_CASES", {
            "ACTION": "C", "TC_PATH": path,
            "TC_REFERENCE": case.get("reference", ""),
            "TC_DESCRIPTION": rich_text(case.get("description", "")),
            "TC_PRE_REQUISITE": rich_text(case.get("prerequisite", "")),
            "TC_KIND": "STANDARD",
            "DRAFTED_BY_AI": int(case.get("drafted_by_ai", False)),
        })
        steps = case.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError(f"Steps must be an array: {path}")
        for number, step in enumerate(steps, 1):
            append("STEPS", {
                "ACTION": "C", "TC_OWNER_PATH": path,
                "TC_STEP_NUM": number, "TC_STEP_IS_CALL_STEP": 0,
                "TC_STEP_ACTION": rich_text(step["action"]),
                "TC_STEP_EXPECTED_RESULT": rich_text(step["expected"]),
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against a concurrent overwrite.
    with output.open("xb") as stream:
        workbook.save(stream)
    print(f"Generated {output}: {rows['TEST_CASES'] - 1} cases, "
          f"{rows['STEPS'] - 1} steps")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.template, args.cases, args.project, args.output)


if __name__ == "__main__":
    main()
