def parse(line):
    fields = line.split(" ", 2)
    if len(fields) != 3:
        return None
    minute, level, message = fields
    if not minute.isascii() or not minute.isdecimal() or level not in ("INFO", "WARN", "ERROR"):
        return None
    return int(minute), level, message
