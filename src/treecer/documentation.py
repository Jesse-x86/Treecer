"""Read the versioned offline manual without accessing project state."""

from importlib.resources import files

from .errors import TreecerError

TOPICS = {
    "quick-start": {"zh": "快速开始", "en": "Quick start"},
    "core-concept": {"zh": "核心概念", "en": "Core concepts"},
    "workflow": {"zh": "讨论工作流", "en": "Discussion workflow"},
    "reference": {"zh": "操作参考", "en": "Reference"},
}


def manual(topic=None, *, english=False):
    language = "en" if english else "zh"
    if topic is None:
        return {"language": language, "topics": [
            {"id": name, "title": titles[language]} for name, titles in TOPICS.items()
        ]}
    if topic not in TOPICS:
        raise TreecerError("UNKNOWN_TOPIC", f"Unknown topic: {topic}", topics=list(TOPICS))
    resource = files("treecer").joinpath("assets", "manual", language, f"{topic}.md")
    return {"language": language, "topic": topic, "title": TOPICS[topic][language],
            "content": resource.read_text(encoding="utf-8")}


def render_manual(result):
    if "content" in result:
        return result["content"].rstrip()
    english = result["language"] == "en"
    heading = "Treecer offline manual" if english else "Treecer 离线手册"
    lines = [heading, ""]
    lines.extend(f"  {item['id']:<14} {item['title']}" for item in result["topics"])
    lines.extend(["", "treecer doc <topic> --en" if english else "treecer doc <主题>（--en 阅读英文）"])
    return "\n".join(lines)
