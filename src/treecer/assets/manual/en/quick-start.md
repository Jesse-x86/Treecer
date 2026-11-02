# Quick start

Treecer stores discussions as resumable trees. The assistant maintains discussion content; the tool handles project discovery, local navigation, and persistence.

## Install

Use Python 3.11 or newer and pipx with its app directory configured on PATH. From a source checkout:

```text
pipx install .
```

You can also install a distribution wheel you received:

```text
pipx install ./treecer-0.1.1-py3-none-any.whl
```

The installed app works outside the source checkout. Explore its entry points:

```text
treecer --help
treecer setup
treecer doc --en
treecer doc quick-start --en
```

`setup` prints connection guidance and the installed skill location. `doc` lists four topics; supply a topic to read it. Manuals default to Chinese; `--en` selects English. Documentation works before project binding and creates no project data.

## Record your first discussion

Enter the workspace you want to track, then run:

```text
treecer context show
treecer task add Topic
treecer tree add "Planning"
treecer node add "Option selection" --note "Open question: how should options be compared?"
```

First use discovers or registers the project, writes `.treecer/project.json` in the workspace, and stores databases in your local user data directory. Creating a task selects it; creating a tree focuses its root. Adding a child preserves the existing focus.

Creation returns an automatically assigned ID. The example below assumes `N2` in a fresh project; use the ID actually returned:

```text
treecer focus N2
treecer context show
```

For a workspace named Project, the prompt is:

```text
Topic@Project# Planning/Option selection [N2]
```

It identifies the task, project, root-to-current path, and node ID. Current node content and direct children follow.

## Record a decision and return

Reading a node returns its `revision`. Assuming the current value is 1:

```text
treecer node update N2 --revision 1 --status 已解决 --note "User decided: compare options against the intended use case"
treecer focus ..
treecer children
```

`focus ..` returns to the parent; `children` lists branches you can continue. Status values remain the literal Chinese API values, including `已解决` (resolved). After finishing a child, the assistant checks what remains in the parent discussion.

## Resume and use multiple chats

Run `context show` again in the same workspace to resume the CLI position. Independent chats or terminals can use stable identities:

```text
treecer context show --source codex --session chat-123
```

Keep the same `--source` and `--session` on later calls, or supply the session through `TREECER_SESSION`. Sources accessing the same project share content while retaining separate conversation positions.

Read `treecer doc reference --en` for MCP connections, parameters, and troubleshooting; `treecer doc core-concept --en` for the data model; and `treecer doc workflow --en` for discussion practice.
