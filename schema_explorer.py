import json
from concurrent.futures import ProcessPoolExecutor
from functools import reduce


def extract_schema(obj, prefix=""):
    """Map: extract all key paths and types from a dict."""
    paths = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            paths[path] = {"types": {type(v).__name__}, "count": 1}
            nested = extract_schema(v, path)
            for p, info in nested.items():
                paths[p] = info
    elif isinstance(obj, list):
        paths[f"{prefix}[]"] = {"types": {"list"}, "count": 1}
        if obj:
            nested = extract_schema(obj[0], f"{prefix}[]")
            for p, info in nested.items():
                paths[p] = info
    return paths


def merge_schemas(a, b):
    """Reduce: merge two schemas, combining types and counts."""
    result = dict(a)
    for k, v in b.items():
        if k in result:
            result[k] = {
                "types": result[k]["types"] | v["types"],
                "count": result[k]["count"] + v["count"],
            }
        else:
            result[k] = v
    return result


if __name__ == "__main__":
    with open("./search_history.json", "r") as f:
        data = json.load(f)

    total = len(data)
    print(f"Processing {total} entries...\n")

    with ProcessPoolExecutor() as executor:
        schemas = list(executor.map(extract_schema, data, chunksize=1000))

    full_schema = reduce(merge_schemas, schemas, {})

    mandatory = []
    optional = []

    for path in sorted(full_schema.keys()):
        info = full_schema[path]
        types = ", ".join(sorted(info["types"]))
        count = info["count"]
        pct = count / total * 100

        if count == total:
            mandatory.append((path, types))
        else:
            optional.append((path, types, count, pct))

    print("=== MANDATORY FIELDS (100%) ===")
    for path, types in mandatory:
        print(f"  {path}: {types}")

    print(f"\n=== OPTIONAL FIELDS ===")
    for path, types, count, pct in optional:
        print(f"  {path}: {types} ({count}/{total}, {pct:.1f}%)")
