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

This preserves the sequence—approval, review, then possible access—and keeps
the actors unspecified. If knowing the actors matters, flag them as missing
instead of guessing.

## Preserve technical literals and host scope

### Before

> In Codex, set `allow_implicit_invocation` to `false`. In Copilot CLI, run
> `/skills reload` after installing or changing a skill.

### Safe revision

> To disable implicit skill invocation in Codex, set
> `allow_implicit_invocation` to `false`.
> After installing or changing a skill, run `/skills reload` in Copilot CLI.

All three technical literals are unchanged, and each action remains scoped to
its original host.
