from format_rules import parse


def solve(value):
    counts = {"INFO": 0, "WARN": 0, "ERROR": 0}
    invalid = 0
    for line in value["lines"]:
        record = parse(line)
        if record is None:
            invalid += 1
            continue
        minute, level, message = record
        if value["start"] <= minute <= value["end"]:
            counts["ERROR" if "ERROR" in message else level] += 1
    return {"counts": counts, "invalid": invalid}
