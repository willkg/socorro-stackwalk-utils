# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Generates diff output between json_dump output from rust minidump-stackwalk
(left) and breakpad stackwalker (right).

This takes into account fields that have ephemeral values, known differences,
and the shape of everything.

"""

import json
import itertools
import re
import sys


USAGE = "Usage: dumpdiff.py RUST_FILE BREAKPAD_FILE"


# These values will always be different
IGNORE_KEYS = [
    # breakpad and minidump-stackwalk have different values for this
    "stackwalk_version",
    # minidump-stackwalk doesn't output these
    "tiny_block_size",
    "largest_free_vm_block",
    "write_combine_size",
    # minidump-stackwalk changed this to frame_count to be more self-consistent
    "crashing_thread.total_frames",
    # these are ephmeral
    "modules.N.symbol_disk_cache_hit",
    "modules.N.symbol_fetch_time",
    "modules.N.missing_symbols",
    "threads.N.frames.N.missing_symbols",
    "crashing_thread.frames.N.missing_symbols",
    # this differs between minidump-stackwalk and stackwalker, but it's fine if
    # it's wrong
    # "modules.N.version",
]


def is_ignore_key(namespace, key):
    if namespace:
        key = f"{namespace}.{key}"
    key = re.sub(r"\d+", "N", key)
    return key in IGNORE_KEYS


# rust-minidump fills in null where stackwalker would omit the key entirely
NULL_OK = [
    "mac_crash_info",
    "lsb_release",
    "crash_info.assertion",
    "system_info.cpu_microcode_version",
    "crashing_thread.last_error_value",
    "crashing_thread.thread_name",
    "crashing_thread.frames.N.line",
    "crashing_thread.frames.N.file",
    "crashing_thread.frames.N.module",
    "crashing_thread.frames.N.module_offset",
    "crashing_thread.frames.N.function_offset",
    "crashing_thread.frames.N.function",
    "threads.N.last_error_value",
    "threads.N.thread_name",
    "threads.N.frames.N.file",
    "threads.N.frames.N.function",
    "threads.N.frames.N.function_offset",
    "threads.N.frames.N.line",
    "threads.N.frames.N.module",
    "threads.N.frames.N.module_offset",
    "modules.N.cert_subject",
    "modules.N.symbol_url",
    "unloaded_modules.N.cert_subject",
]


def is_null_ok(namespace, key):
    if namespace:
        key = f"{namespace}.{key}"
    key = re.sub(r"\d+", "N", key)
    return key in NULL_OK


FALSE_OK = [
    "modules.N.loaded_symbols",
    "modules.N.corrupt_symbols",
]


def is_false_ok(namespace, key):
    if namespace:
        key = f"{namespace}.{key}"
    key = re.sub(r"\d+", "N", key)
    return key in FALSE_OK


def get_data(fn):
    with open(fn, "r") as fp:
        data = json.load(fp)

    # If this is a processed crash, then we get the json_dump part of it
    if "json_dump" in data:
        return data["json_dump"]

    # If this is minidump-stackwalk output, then we return the whole thing
    return data


def fix_value(value):
    return json.dumps(value)


def compare_hex(key, left, right):
    # Handle None values first
    if left is None or right is None:
        return left == right

    try:
        left_int = int(left, base=16)
    except TypeError:
        return False
    try:
        right_int = int(right, base=16)
    except TypeError:
        return False
    return left_int == right_int


def compare_misc(key, left, right):
    return left == right


KEY_COMPARE = {
    "module_offset": compare_hex,
    "offset": compare_hex,
    "function_offset": compare_hex,
}


def print_line(key, leftvalue, indicator, rightvalue):
    TRIM = 80
    leftvalue = leftvalue[:TRIM]
    rightvalue = rightvalue[:TRIM]
    print(f"{key:50}  {leftvalue:{TRIM}}  {indicator}  {rightvalue}")


def diff_lists(namespace, left, right, recurse=False):
    for i, values in enumerate(itertools.zip_longest(left, right, fillvalue=None)):
        left_val, right_val = values

        if left_val is not None and right_val is None:
            print_line(f"{namespace}.{i}", f"{left_val}", ">", "")

        elif left_val is None and right_val is not None:
            print_line(f"{namespace}.{i}", "", "<", f"{right_val}")

        else:
            if isinstance(left_val, dict) or isinstance(right_val, dict):
                if recurse:
                    diff_dicts(f"{namespace}.{i}", left_val, right_val, recurse=True)
                continue

            if isinstance(left_val, list) or isinstance(right_val, list):
                if recurse:
                    diff_lists(f"{namespace}.{i}", left_val, right_val, recurse=True)
                continue

            if not compare_misc(namespace.split(".")[-1], left_val, right_val):
                print_line(
                    f"{namespace}.{i}",
                    f"{fix_value(left_val)}",
                    "|",
                    f"{fix_value(right_val)}",
                )


def diff_dicts(namespace, left, right, recurse=False):
    all_keys = set(left.keys()).union(set(right.keys()))
    for key in all_keys:
        if is_ignore_key(namespace, key):
            continue

        if namespace:
            nkey = f"{namespace}.{key}"
        else:
            nkey = key

        if key in left and key not in right:
            if left[key] is None and is_null_ok(namespace, key):
                continue
            elif left[key] is False and is_false_ok(namespace, key):
                continue
            print_line(nkey, f"{fix_value(left[key])}", ">", "")

        elif key not in left and key in right:
            print_line(nkey, "", "<", f"{fix_value(right[key])}")

        else:
            left_val = left[key]
            right_val = right[key]

            if isinstance(left_val, dict) or isinstance(right_val, dict):
                if recurse:
                    left_val = left.get(key, {})
                    right_val = right.get(key, {})
                    diff_dicts(nkey, left_val, right_val, recurse=True)
                continue

            if isinstance(left_val, list) or isinstance(right_val, list):
                if recurse:
                    diff_lists(nkey, left_val, right_val, recurse=True)
                continue

            comparator = KEY_COMPARE.get(key, compare_misc)
            if not comparator(key, left_val, right_val):
                print_line(
                    nkey, f"{fix_value(left_val)}", "|", f"{fix_value(right_val)}"
                )


def main():
    if len(sys.argv) != 3:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    fn1, fn2 = sys.argv[1:]
    try:
        left = get_data(fn1)
    except KeyError:
        left = {}
    try:
        right = get_data(fn2)
    except KeyError:
        right = {}

    print(f"diffing {fn1} and {fn2}")

    # Diff roots
    diff_dicts("", left, right)

    # Diff crash_info
    diff_dicts("crash_info", left.get("crash_info", {}), right.get("crash_info", {}))

    # Diff system info
    diff_dicts("system_info", left.get("system_info", {}), right.get("system_info", {}))

    # Diff sensitive
    diff_dicts("sensitive", left.get("sensitive", {}), right.get("sensitive", {}))

    # Diff crashing thread
    diff_dicts(
        "crashing_thread",
        left.get("crashing_thread", {}),
        right.get("crashing_thread", {}),
        recurse=True,
    )

    # Diff crashing thread
    diff_lists(
        "threads", left.get("threads", {}), right.get("threads", {}), recurse=True
    )

    # Diff modules and unloaded modules
    # Modules can be ordered differently, so we're going to sort them, then diff them
    def module_key(module):
        return module.get("filename", "") + module.get("code_id", "")

    left_modules = left.get("modules", [])
    left_modules.sort(key=module_key)
    right_modules = right.get("modules", [])
    right_modules.sort(key=module_key)
    diff_lists("modules", left_modules, right_modules, recurse=True)

    left_unloaded_modules = left.get("unloaded_modules", [])
    left_unloaded_modules.sort(key=module_key)
    right_unloaded_modules = right.get("unloaded_modules", [])
    right_unloaded_modules.sort(key=module_key)
    diff_lists(
        "unloaded_modules", left_unloaded_modules, right_unloaded_modules, recurse=True
    )


if __name__ == "__main__":
    main()
