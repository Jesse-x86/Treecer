"""Treecer paths are discussion addresses, independent of host filesystem paths."""

from urllib.parse import unquote

from .errors import TreecerError


def segment(title):
    if title in (".", "..", "~"):
        return "".join(f"%{ord(char):02X}" for char in title)
    return (
        title.replace("%", "%25")
        .replace("/", "%2F")
        .replace("\n", "%0A")
        .replace("\r", "%0D")
    )


def absolute(parts):
    return "/" + "/".join(segment(part) for part in parts)


def display(parts, home):
    if home and parts[: len(home)] == home:
        tail = parts[len(home) :]
        return "~" + ("/" + "/".join(segment(part) for part in tail) if tail else "")
    return absolute(parts)


def normalize(path, cwd, home):
    if path is None:
        return list(cwd)
    if path == "~" or path.startswith("~/"):
        if not home:
            raise TreecerError(
                "TASK_REQUIRED", "请先用 task add 或 task use 选择当前任务。"
            )
        result = list(home)
        rest = path[1:]
    elif path.startswith("/"):
        result, rest = [], path
    else:
        result, rest = list(cwd), path
    for item in rest.split("/"):
        if not item or item == ".":
            continue
        if item == "..":
            if result:
                result.pop()
        else:
            try:
                result.append(unquote(item, errors="strict"))
            except UnicodeError as error:
                raise TreecerError(
                    "INVALID_PATH", "路径段需要使用有效的 UTF-8 编码。"
                ) from error
    return result
