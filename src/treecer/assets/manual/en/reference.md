# Reference

## Entry points and common options

```text
treecer --help
treecer --version
treecer setup
treecer doc --en
treecer doc quick-start --en
```

Topics: quick-start, core-concept, workflow, reference. Omit the topic for an index. Chinese is the default; --en selects English. --json returns the index or topic as structured data. Documentation requires no project binding.

| Option | Purpose |
| --- | --- |
| --home | Data directory; overrides TREECER_HOME and the default |
| --workspace / -C | Actual workspace; CLI defaults to its working directory |
| --project / -p | Manually select and pin a project by name |
| --source | Source identity; defaults to cli |
| --session | Stable chat identity; takes priority over TREECER_SESSION |
| --json | Structured output |
| --sudo | Confirm this cross-task write; also available as treecer sudo prefix |

Options can appear at the root or after the leaf command. Quote "~/..." in shells to preserve Treecer's task-root semantics.

## Projects and tasks

```text
treecer projects
treecer context show
treecer context use --project Project --task Topic
treecer context reset
treecer task list
treecer task list --at "/OtherProject"
treecer task add Topic
treecer task use Topic
```

task add creates and selects a task and its root. task use selects by unique name and restores its position. Each task is one tree; create discussion topics with node add.

Resolution uses an explicit project, a pinned session binding, actual-workspace discovery, then an existing binding when no workspace was supplied. Discovery walks upward for .treecer/project.json or registered paths, stopping at a Git root when encountered. No match registers a new project; duplicate workspace names receive distinct suffixed names.

context reset clears a project pin and rediscovers it, preserving content, task selections, and positions. Project names and task names within a project are unique, with exact character and case matching.

## Paths, reads, and navigation

```text
treecer context show "~/Planning"
treecer node get "~/Planning/Option"
treecer path "~/Planning/Option"
treecer parent "~/Planning/Option"
treecer children "~" --limit 20 --offset 0
treecer find Option --at "/Project/Topic" --limit 20
treecer focus "~/Planning/Option"
treecer focus ..
treecer focus "~"
```

~ is the bound task root; `/project/task/node` is absolute; relative paths start at focus. / lists projects; /project lists tasks. A task root's parent is its project directory; the global root has no parent.

Read results contain prompt, current, target, source, session, and operation data such as node, ancestors, or children. prompt is always the saved position. current.project/task identify the binding; target identifies the operated-on object. node contains title, path, absolute_path, parent, note, status, and revision. Internal IDs stay in storage.

Reads preserve focus. focus explicitly navigates; cross-task focus retains the home binding and shows an absolute location. Cross-task content reads, children, parent, and search require no sudo.

Children use creation order, preserved across content updates. Default page size is 50; limit must be positive and offset nonnegative. next_offset indicates a later page. find uses literal title substring matching, defaulting to the current task; --at selects a subtree, project, or the global namespace.

## Create, update, and move

```text
treecer node add "Planning" --parent "~"
treecer node add Option --parent "~/Planning" --note "Open question: ..."
treecer node update "~/Planning/Option" --revision 3 --title "Option selection" --status 暂放 --note "Return when: ..."
treecer node move "~/Planning/Option selection" "~/Other topic" --revision 4
```

Use actual returned revisions. Creation and ordinary updates preserve focus. Renames and moves preserve internal identity and saved focus follows the new path. Sibling names must be unique; separate branches may repeat names. Encode slash, percent, line breaks, and entire names ., .., ~ using core-concept's segment rules.

Updates change supplied fields only; --note '' clears content. Literal statuses are 讨论中, 已解决, 暂放, 已取消. Task roots allow content and status updates; their names and locations derive from task identity. Moves reject collisions and cycles and support complete branches across tasks and projects.

Cross-task writes without sudo return SUDO_REQUIRED, identifying the current task, target ownership and path, and a current-task path candidate. Confirm and retry:

```text
treecer sudo node update "/Project/OtherTopic/Planning" --revision 5 --note "Target checked"
```

The override retains the binding and selected node; moving that selected node updates its displayed path. Later requests are checked anew. Moves check both source and destination ownership. task use / context use explicitly change the binding; focus navigates.

## MCP

Use the client's server configuration format:

```json
{
  "command": "treecer",
  "args": ["mcp", "--workspace", "/absolute/path/to/project", "--source", "my-assistant"]
}
```

command may be a visible executable or its absolute path. Communication is stdio, logging is stderr. Tools: context, projects, tasks, use_task, add_node, update_node, move_node, path, parent, children, find_nodes, focus, reset_context.

- context(path?) returns context. path, parent, children, and find_nodes also use paths.
- tasks lists without title and creates with title. use_task(title) selects by name.
- add_node(title,parent?,note?,sudo?) creates children; update_node(path,revision,...) updates fields.
- move_node(path,new_parent,revision,sudo?) moves branches; cross-task writes explicitly supply sudo=true.
- focus(path) saves position; reset_context clears the project pin.

Tool scope can provide workspace, project name, source, and session. Each chat keeps a stable session. A generated default is returned when none was supplied; provide it again after restart. MCP does not infer the user's workspace from the service launch directory. Without a workspace, explicit project, or existing binding it returns CONTEXT_REQUIRED.

## Data and upgrades

Default data: %LOCALAPPDATA%\Treecer on Windows, ~/.local/share/Treecer elsewhere. Override with TREECER_HOME or --home.

catalog.sqlite stores projects, workspaces, bindings, and positions. projects/<internal-project-identity>/project.sqlite stores each project's tasks and nodes. Local SQLite transactions and rollback journals commit cross-project moves and position following together.

On first access, 0.1.2 transactionally migrates 0.1.1 data: old tree roots become topics beneath task roots, preserving content, status, and resume positions. Legacy project-level topics move into a new inbox task; occupied names use inbox (2), etc. The new interface uses paths. Stop old-version service processes before upgrading.

Duplicate legacy task or resulting sibling names produce MIGRATION_CONFLICT and roll back that project's migration, preserving its data until the new names are determined. For backup, stop relevant processes and copy the complete data directory and workspace markers. Check context show after restoration.

## Errors

- SUDO_REQUIRED: check ownership, then explicitly override or correct the path.
- REVISION_CONFLICT: merge current content and submit its latest revision.
- DUPLICATE_NAME: choose another sibling name or update the existing node.
- NODE_NOT_FOUND / TASK_NOT_FOUND / PROJECT_NOT_FOUND: check path and data directory; node errors include the nearest existing ancestor.
- TASK_REQUIRED / NODE_REQUIRED: select a task or node.
- INVALID_MOVE / ROOT_OPERATION: preserve acyclic relationships and task roots.
- TARGET_CHANGED: reread the path after concurrent movement.
- MIGRATION_CONFLICT: original content remains; determine distinct names.
- STORE_BUSY: refresh and retry later.

CLI failures return nonzero exit codes. MCP returns tool errors.
