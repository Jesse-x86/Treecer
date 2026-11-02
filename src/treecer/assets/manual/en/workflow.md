# Discussion workflow

## Start at the current position

Use `treecer context show --json` or MCP context to inspect the binding, saved position, content, ancestors, and direct children. Verify the discussion object before continuing.

A new project starts with a task directory. Select existing work with task use or MCP use_task; create new work with task add or MCP tasks(title=...). Each task has a `~` root with topic nodes beneath it.

## Record decisions and questions

Organize the note as useful, for example:

```text
Purpose: How can an assistant resume its discussion position?
User decided: Separate projects and tasks; persist session positions.
Assistant suggestion: Save positions per source and session.
Open question: How does the host supply a stable session identity?
Next step: Exercise a client restart.
```

Distinguish user decisions, assistant proposals, and unresolved questions. Keep remaining gaps when only part is settled. State missing evidence explicitly.

## Branch and defer

node add or MCP add_node creates a question beneath the current node, or a supplied parent path. Creation returns its new path while retaining focus. Use focus when actually entering it.

For a deferred branch, record its question and return condition and set status to 暂放. Sibling names are unique; full paths distinguish repeated names across branches.

## Conclude and return

Read before editing and submit the returned revision. Assuming the actual value is 4:

```text
treecer node get "~/Planning/Option" --json
treecer node update "~/Planning/Option" --revision 4 --status 已解决 --note "User decided: ..."
treecer parent
treecer focus ..
treecer children
```

Check which part of the parent was resolved, return to it, and select an unfinished sibling. Parent status changes explicitly. Users can change discussion order at any time.

Reopen with 讨论中. When a decision supersedes a proposal, update the effective conclusion and preserve useful reasons.

## Read other tasks and collaborate

Use `/project/task/node` to consult other tasks. Reads preserve the binding and focus; results carry the actual target path. For an intended cross-task write, check the warning's target and explicitly provide sudo on that request.

For REVISION_CONFLICT, merge still-valid information from current and submit its revision. After renames or moves, use returned paths; saved positions follow internal identities.

Each chat keeps a stable source/session. Content is shared; positions are independent. A non-null next_offset indicates another children/search page.

Update at important conclusions, branches, direction changes, or a discussion round's end. Keep conversation substantive. Discussion records follow the current task's authorization; code, architectural-intent changes, deployment, and external actions follow their respective task authorizations.
