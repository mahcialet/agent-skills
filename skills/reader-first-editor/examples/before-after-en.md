# English Before / After

## Preserve actor uncertainty

### Before

> After approval, the request is reviewed before access may be granted.

### Unsafe revision

> After the manager approves the request, the support team reviews it and
> grants access.

This revision invents two actors. It also changes possible access (`may`) into
a guaranteed outcome, so readers could act on a promise the source never made.

### Safe revision

> After approval, the request is reviewed. Access may then be granted.

The revision preserves the original sequence—approval, review, then possible
access—without inventing actors. If knowing the actors matters, flag them as
missing instead of guessing.

## Preserve technical literals and host scope

### Before

> In Codex, set `allow_implicit_invocation` to `false`. In Copilot CLI, run
> `/skills reload` after installing or changing a skill.

### Safe revision

> To disable implicit skill invocation in Codex, set
> `allow_implicit_invocation` to `false`.
> After installing or changing a skill, run `/skills reload` in Copilot CLI.

The revision leaves all three technical literals unchanged. It also makes the
host scope explicit: the setting applies to Codex, while the reload command
applies to Copilot CLI.
