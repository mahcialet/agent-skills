# English Before / After

## Preserve actor uncertainty

### Before

> After approval, the request is reviewed before access may be granted.

### Unsafe revision

> After the manager approves the request, the support team reviews it and
> grants access.

This invents two actors and changes possible access (`may`) into a guaranteed
outcome.

### Safe revision

> After approval, the request is reviewed. Access may then be granted.

The sequence and uncertainty remain. If knowing the actors matters, flag them
as missing instead of guessing.

## Preserve technical literals and host scope

### Before

> In Codex, set `allow_implicit_invocation` to `false`. In Copilot CLI, run
> `/skills reload` after installing or changing a skill.

### Safe revision

> To disable implicit skill invocation in Codex, set
> `allow_implicit_invocation` to `false`.
> After installing or changing a skill in Copilot CLI, run `/skills reload`.

Both literals and each command's host scope are unchanged.
