# Core concepts

## Projects, tasks, and nodes

A project is an independent workspace, such as Project or a another project, with its own database. A task is ongoing project work that can continue across chats. Each task owns a discussion tree rooted at ~; topics and questions are nodes beneath it.

Task names are unique within a project. Node names are unique among siblings; separate branches can use the same name. Names match original characters and case exactly. Stable identities maintain internal relationships and positions; public operations use names and paths.

## Address space

| Path | Meaning |
| --- | --- |
| / | Global Treecer project directory |
| /Project | The project's task directory |
| /Project/Topic | A specified task root |
| ~ | The currently bound task root |
| ~/Planning | Relative to the task root |
| Child question | Relative to the current discussion position |
| . / .. | Current position / parent |

The prompt `Topic@Project: ~/Planning/Option$` corresponds to `/Project/Topic/Planning/Option`. The trailing $ is a prompt marker, not path content.

Segments encode / as %2F, % as %25, and line breaks as %0A or %0D. Entire names ., .., and ~ encode as %2E, %2E%2E, and %7E. Segments are decoded after splitting, preserving these characters in node titles.

## Binding, focus, and target

The current task defines ~. Focus identifies the current discussion node or a project/global directory. prompt always describes saved focus; target and node describe this operation's object.

Reads, creation, updates, and moves do not deliberately switch focus. focus is explicit navigation. Focusing another task preserves the home task binding and displays an absolute location; writes there still require cross-task confirmation. task use changes the binding and restores that task's saved position.

Renames and moves preserve internal identity, so saved positions follow nodes to their new paths, including across projects. Callers should update cached path references from returned results.

## Content and revision

The Markdown note can record purpose, user decisions, assistant suggestions, open questions, and next steps. Literal statuses are 讨论中 (in discussion), 已解决 (resolved), 暂放 (deferred), and 已取消 (cancelled), changed explicitly.

revision identifies a content version. Read it before updates or moves. Conflicts return REVISION_CONFLICT and current content for merging. Revisions also detect stale writes when an old path is occupied by a different node.

## Sources and sessions

A source identifies an integration; a session identifies its chat. Project content is shared, while sources/sessions retain separate task selections and positions. Returning to a task restores its saved position.

CLI defaults to workspace-based resumption; use --source, --session, or TREECER_SESSION to distinguish chats. MCP uses scope.source and scope.session. A generated session is returned when none was supplied; provide it again after restart.

## Cross-task operations

Reads, children, paths, and search can access other tasks directly. Writes to another task's content or structure require sudo on the current request. Without it, the result names the current task, target task and path, and a correction candidate, leaving data intact.

sudo is an internal Treecer request confirmation with no password. Normalize ~, relative segments, and .. before checking the final task ownership. The override preserves the binding and is checked anew on later requests.
