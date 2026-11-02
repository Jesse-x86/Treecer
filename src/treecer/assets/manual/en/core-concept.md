# Core concepts

## Projects, tasks, trees, and nodes

- A project is an independent workspace, such as Project or a another project. Each project has its own database, with a stable ID separate from its display name.
- A task is ongoing work within a project, such as Topic design. It can continue across multiple chats and assistants.
- A discussion tree belongs to a project and can be associated with a task. A null task makes it a project-level tree. A task can contain multiple trees.
- A node stores a question, title, content, status, and parent relationship. Each tree has one root; parent relationships stay within the tree and remain acyclic.

Project-level trees can hold ideas before they become a specific task. The assistant selects or creates tasks from the user's discussion; a new session starts at the project overview.

## Identity and names

Project IDs are generated automatically. Task IDs use `T…`, tree IDs `R…`, and node IDs `N…`; the tool assigns them all. Node IDs are unique within a project. Different projects may reuse the same node number, so a complete reference includes its project.

Node titles may repeat. Renaming or moving a node preserves its ID. Title search returns IDs and ancestor paths; use the selected ID for operations. Use task IDs to distinguish duplicate task titles.

## Location prompt

```text
Topic@Project# Planning/Option/Comparison criteria [N27]
```

The first part identifies the task and project; the rest is the root-to-current path. `~` means no selected task; `/` means no selected node.

The tool follows parent links from the current node to produce the latest path. Prompt segments escape `/`, `%`, and line breaks. Structured JSON paths retain original titles and each segment's ID.

## Content, status, and revision

The Markdown `note` can record the question's purpose, user decisions, assistant suggestions, open questions, and next steps.

Status values are the literal API strings `讨论中` (in discussion), `已解决` (resolved), `暂放` (deferred), and `已取消` (cancelled). An open node can contain partial decisions. Parent status changes explicitly. Deferred nodes remain visible and can describe when to return.

`revision` is a node's revision number. Reads return it; updates and moves supply the revision they were based on. If another call changed the node, the tool returns a conflict and its current content so the assistant can merge before submitting again.

## Sources, sessions, and resume positions

A source identifies an entry point, such as codex or another assistant. A session identifies a particular chat within that source. Together they identify the project binding and the selected task, tree, and node within the project.

Sessions can share a tree while retaining their own positions. Reads and child creation preserve focus; `focus` changes it. CLI resumes by workspace by default. Independent chats can pass `--source` and `--session`; MCP passes `scope.source` and `scope.session`.

## Project discovery and storage

CLI uses its working directory or `--workspace`. MCP uses the workspace supplied in startup or tool arguments. `.treecer/project.json` stores the stable project ID. The user data directory's `catalog.sqlite` stores projects and workspace mappings; `projects/<project-ID>/project.sqlite` stores project content and positions.

An explicit project selection pins the session to that project. Clearing the pin enables workspace discovery again. See `treecer doc reference --en` for precedence, storage locations, and recovery.
