# Quick start

Treecer lets assistants save and resume discussions through names and paths:

```text
Topic@Project: ~/Planning/Option selection$
```

## Install

Use Python 3.11+ and pipx with its app directory on PATH:

```text
pipx install ./treecer-0.1.2-py3-none-any.whl
```

From a source checkout, use `pipx install .`. The installed app works outside that checkout:

```text
treecer --help
treecer setup
treecer doc --en
treecer doc quick-start --en
```

Manuals default to Chinese; --en selects English. Documentation creates no project data. setup prints connection guidance and the installed skill location.

## Create a task and topic

Enter your workspace, for example a directory named Project:

```text
treecer context show
treecer task add Topic
treecer node add "Planning"
treecer focus "~/Planning"
treecer node add "Option selection" --note "Open question: how should options be compared?"
```

First use discovers or registers a project. task add creates and selects a task's ~ root. node add returns the new node's path while preserving focus. focus explicitly changes the discussion position.

Quote "~/..." in a shell so it reaches Treecer unchanged, rather than expanding to the operating system's home directory.

```text
treecer focus "~/Planning/Option selection"
treecer context show
```

The result contains current content, ancestors, and direct children. The prompt always describes saved focus; the operated-on node has a separate path. Internal identities are maintained by the tool; callers use paths.

## Record a conclusion and return

Read the node and submit its revision. Revision 3 below matches this fresh example; use the value actually returned:

```text
treecer node get "~/Planning/Option selection" --json
treecer node update "~/Planning/Option selection" --revision 3 --status 已解决 --note "User decided: compare options against the intended use case"
treecer focus ..
treecer children
```

Literal status values are 讨论中 (in discussion), 已解决 (resolved), 暂放 (deferred), and 已取消 (cancelled). After finishing a child, check the parent's remaining questions and deferred branches.

## Other tasks

An absolute path selects a project, task, and node:

```text
treecer context show "/Project/OtherTopic/Planning"
```

The path must exist. Cross-task reads are allowed and preserve the current binding and position. Cross-task writes stop with a warning naming the target; confirm by retrying with `treecer sudo <original command>` or --sudo. The override applies to that request only.

## Resume

CLI resumes by workspace by default. Independent chats or terminals can keep the same --source and --session, or provide the session through TREECER_SESSION. task use selects a task by name and restores its position.

MCP uses scope.workspace and a stable scope.session. Mutating tools take sudo=true for an explicit cross-task write. See `treecer doc reference --en` for parameters and migration details.
