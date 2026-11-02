# Reference

## CLI entry points and common options

```text
treecer --help
treecer --version
treecer setup
treecer doc --en
treecer doc quick-start --en
treecer doc core-concept --en
```

Topics are `quick-start`, `core-concept`, `workflow`, and `reference`. Omit the topic for an index. Chinese is the default; `--en` selects English. `doc --json` returns the index; `doc <topic> --json` returns language, topic, title, and content. Manuals ship with the installed version and require no project initialization.

Common options can appear at the root command or after the leaf command:

| Option | Purpose |
| --- | --- |
| `--home` | User data directory; overrides TREECER_HOME and the default |
| `--workspace` / `-C` | Actual workspace; CLI defaults to its working directory |
| `--project` / `-p` | Select and pin a project by ID or unique name |
| `--source` | Source identity; defaults to cli for CLI calls |
| `--session` | Stable session identity; takes priority over TREECER_SESSION |
| `--json` | Structured output for data commands and doc |

`setup` prints connection guidance and the installed skill location. `mcp` starts a stdio protocol server.

## Projects, tasks, and trees

```text
treecer projects
treecer context show
treecer context use --project Project
treecer context use --project Project --task Topic
treecer context reset
treecer task list
treecer task add Topic
treecer task use T1
treecer tree list
treecer tree list --task T1
treecer tree add "Planning" --task T1 --note "Purpose: ..."
treecer tree add "Project ideas" --project-level
treecer focus --tree R1
treecer focus --task T1
treecer focus --project-level
```

Select tasks by ID or a unique exact title. Duplicate titles return matches; choose an ID. `task add` selects its task; `tree add` focuses its new root. `focus --task` selects a task overview; `focus --project-level` selects the project-level overview. `tree list` defaults to the current task; `--project-level` lists project-level trees.

Project resolution uses: explicit project, manually pinned session binding, actual-workspace discovery, then an existing session binding when no workspace is supplied. Discovery walks upward for markers or registered paths and uses a Git root when encountered. With no match, it registers a new project. Workspaces with duplicate names receive distinct suffixed project names.

Explicit `--project` pins the source/session to that project. `context reset` clears the binding and rediscovers from the workspace, retaining project content and saved positions.

## Nodes and local navigation

```text
treecer node get N27 --tree R1
treecer context show
treecer path N27
treecer parent N27
treecer children N27 --limit 20 --offset 0
treecer find Option --tree R1 --limit 20 --offset 0
treecer node add "Comparison criteria" --parent N27 --note "Open question: ..."
treecer node update N28 --revision 1 --title "Candidate ranking" --status 暂放 --note "Return when: ..."
treecer node move N28 N30 --revision 2
treecer focus N28
treecer focus ..
```

Use actual returned IDs and revisions. Explicit node IDs are project-local; optional `--tree` checks tree ownership. Without a node, use session focus. Supplying only a tree selects its root for reading. The root has an empty parent path; `focus ..` stays at the root when already there.

Reads and child creation preserve focus. `context show` and `node get` return content, ancestors, and direct children. `children` returns only direct child IDs, titles, and statuses. Pagination defaults to 50; limit must be positive and offset nonnegative. A non-null `next_offset` identifies the next page. Title search uses literal substring matching and returns paths.

Literal status values are `讨论中` (in discussion), `已解决` (resolved), `暂放` (deferred), and `已取消` (cancelled). Updates change supplied fields only; `--note ''` clears content. Updates and moves require the read revision. `REVISION_CONFLICT` includes the current node; merge before submitting again. Moves preserve all branch IDs and maintain same-tree, single-root, and acyclic relationships.

Prompt paths escape `/`, `%`, and line breaks. JSON paths retain original titles and segment IDs. Names support display; IDs locate objects.

## MCP connection

Place a server entry in your client's own configuration format. Set command to the treecer executable visible to the client or its absolute path:

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "V:/work/Project", "--source", "codex"]
}
```

Startup accepts common options. The service communicates over stdio and logs to stderr. Server instructions, tool descriptions, and parameter schemas guide calls.

Tools: `context`, `projects`, `tasks`, `trees`, `add_node`, `update_node`, `move_node`, `path`, `parent`, `children`, `find_nodes`, `focus`, and `reset_context`.

- `tasks` lists tasks without title; supplying title creates and selects a task.
- `trees` lists trees without title; supplying title creates and focuses a tree. task selects a task; project_level selects project-level trees.
- `context` returns an overview or node context; `add_node` defaults to the current parent.
- `update_node` and `move_node` take the read revision, with fields and effects corresponding to CLI operations.
- `focus` saves position; node_id can be `..`. `reset_context` clears the session's project binding so a later call rediscovers it.

Tool scope can supply the actual workspace and chat identity:

```json
{
  "scope": {
    "workspace": "V:/work/Project",
    "source": "codex",
    "session": "host-chat-123"
  }
}
```

Scope fields are optional. Workspace comes from startup or tool arguments; project manually pins the project. After initial resolution, the same source/session can restore its existing binding. Each chat should keep its own session. The server returns a generated default session when none was supplied; provide it again after restart, or use `--session` / `TREECER_SESSION`.

MCP uses an explicitly supplied actual workspace. With no workspace, explicit project, or existing binding, it returns `CONTEXT_REQUIRED`; supply scope once to continue.

## Data, backup, and errors

The default data directory is `%LOCALAPPDATA%\Treecer` on Windows and `~/.local/share/Treecer` elsewhere. Override it with `TREECER_HOME` or `--home`. It contains:

```text
catalog.sqlite
projects/<project-ID>/project.sqlite
```

The catalog stores projects, workspaces, and session project bindings. Each project database stores tasks, trees, nodes, and positions. Workspace `.treecer/project.json` markers accompany the matching data directory. Local processes share access through WAL, foreign keys, and short transactions; node revisions detect stale edits.

For backup, stop the relevant Treecer processes and copy the complete data directory and workspace markers. Preserve any `-wal` / `-shm` files left after abnormal exit. After restoring matching files, use `context show` to check project and position.

| Error | Action |
| --- | --- |
| CONTEXT_REQUIRED | Supply an actual workspace or registered project |
| PROJECT_NOT_FOUND | Check project selection, data directory, and marker belong together |
| INVALID_MARKER / PROJECT_MISMATCH | Check marker or database identity; restore the correct files |
| NODE_REQUIRED | Focus a node, select a tree, or create one |
| NODE_NOT_FOUND / TREE_NOT_FOUND / TASK_NOT_FOUND | Query the current project for the actual ID |
| AMBIGUOUS_TASK | Select a returned task ID |
| TREE_MISMATCH / TASK_MISMATCH | Check node, tree, and task ownership |
| INVALID_MOVE | Choose a valid same-tree parent while preserving root and acyclic relationships |
| REVISION_CONFLICT | Merge the current content and submit its latest revision |
| STORE_BUSY / WORKSPACE_CHANGED | Retry later after refreshing relevant context |

CLI failures print errors and return nonzero exit codes. MCP reports tool errors. Unknown documentation topics report available names through command help.
