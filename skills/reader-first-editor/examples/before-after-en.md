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

> Access may be granted after approval and review of the request.

The sequence and uncertainty remain. If knowing the actors matters, flag them
as missing instead of guessing.

## Preserve technical literals

### Before

> Set `allow_implicit_invocation` to `false`, then run `/skills reload`.

### Safe revision

> To disable implicit invocation, set `allow_implicit_invocation` to `false`.
> Then run `/skills reload`.

Both literals and the operation order are unchanged.
