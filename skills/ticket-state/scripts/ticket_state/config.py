"""Trusted user configuration, target normalization, and write policy."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from .errors import ConfigurationError, IdentityError, PermissionDenied
from .model import TicketIdentity

PERMISSIONS = frozenset({"description:write", "comment:append"})
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
BACKLOG_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-[1-9][0-9]*$")
REDMINE_ID_RE = re.compile(r"^[1-9][0-9]*$")


def _normalized_base_url(raw: str) -> str:
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError("base_url contains an invalid port or host") from exc
    if parsed.scheme.lower() != "https":
        raise ConfigurationError("base_url must use https")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError("base_url must have a host and no userinfo")
    if parsed.query or parsed.fragment:
        raise ConfigurationError("base_url must not contain query or fragment")
    host = parsed.hostname.lower()
    host_literal = f"[{host}]" if ":" in host else host
    netloc = f"{host_literal}:{port}" if port and port != 443 else host_literal
    path = "/" + "/".join(part for part in parsed.path.split("/") if part)
    if path == "/":
        path = ""
    return urlunsplit(("https", netloc, path, "", ""))


@dataclass(frozen=True, slots=True)
class InstanceConfig:
    name: str
    provider: str
    base_url: str
    api_key_env: str

    def api_key(self) -> str:
        value = os.environ.get(self.api_key_env)
        if not value:
            raise ConfigurationError(
                f"API key environment variable is not set: {self.api_key_env}"
            )
        return value


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    name: str
    instance: InstanceConfig
    project_id: int
    project_key: str | None
    read_scope: str
    markup: str
    template: str | None
    write_allowlist: dict[str, frozenset[str]]
    concurrency: str


@dataclass(frozen=True, slots=True)
class Config:
    path: Path
    instances: dict[str, InstanceConfig]
    profiles: dict[str, ProfileConfig]

    def profile(self, name: str) -> ProfileConfig:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown profile: {name}") from exc


def default_config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "agent-skills" / "ticket-state" / "config.toml"


def default_state_root() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "agent-skills" / "ticket-state"


def _only_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigurationError(f"{label} contains unknown keys: {', '.join(unknown)}")


def load_config(path: Path) -> Config:
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"cannot load config {path}: {exc}") from exc
    _only_keys(raw, {"schema_version", "instances", "profiles"}, "config")
    if raw.get("schema_version") != 1:
        raise ConfigurationError("config schema_version must be 1")
    raw_instances = raw.get("instances")
    raw_profiles = raw.get("profiles")
    if not isinstance(raw_instances, dict) or not raw_instances:
        raise ConfigurationError("instances must be a non-empty table")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise ConfigurationError("profiles must be a non-empty table")

    instances: dict[str, InstanceConfig] = {}
    instance_identities: set[tuple[str, str]] = set()
    for name, item in raw_instances.items():
        if not isinstance(item, dict):
            raise ConfigurationError(f"instance {name} must be a table")
        _only_keys(item, {"provider", "base_url", "api_key_env"}, f"instance {name}")
        provider = item.get("provider")
        if provider not in {"backlog", "redmine"}:
            raise ConfigurationError(f"instance {name} has unsupported provider")
        api_key_env = item.get("api_key_env")
        if not isinstance(api_key_env, str) or not ENV_NAME_RE.fullmatch(api_key_env):
            raise ConfigurationError(f"instance {name} has invalid api_key_env")
        base_url = item.get("base_url")
        if not isinstance(base_url, str):
            raise ConfigurationError(f"instance {name} requires base_url")
        if provider == "backlog" and urlsplit(base_url).path not in {"", "/"}:
            raise ConfigurationError(f"Backlog instance {name} must not use a base URL path")
        normalized_url = _normalized_base_url(base_url)
        instance_identity = (provider, normalized_url)
        if instance_identity in instance_identities:
            raise ConfigurationError(f"instance {name} duplicates another provider/base_url")
        instance_identities.add(instance_identity)
        instances[name] = InstanceConfig(
            name=name,
            provider=provider,
            base_url=normalized_url,
            api_key_env=api_key_env,
        )

    profiles: dict[str, ProfileConfig] = {}
    for name, item in raw_profiles.items():
        if not isinstance(item, dict):
            raise ConfigurationError(f"profile {name} must be a table")
        _only_keys(
            item,
            {
                "instance",
                "project_id",
                "project_key",
                "read_scope",
                "format",
                "template",
                "write_allowlist",
                "concurrency",
            },
            f"profile {name}",
        )
        instance_name = item.get("instance")
        if instance_name not in instances:
            raise ConfigurationError(f"profile {name} refers to unknown instance")
        project_id = item.get("project_id")
        if not isinstance(project_id, int) or isinstance(project_id, bool) or project_id <= 0:
            raise ConfigurationError(f"profile {name} requires a positive project_id")
        read_scope = item.get("read_scope", "project")
        if read_scope != "project":
            raise ConfigurationError(f"profile {name} read_scope must be project")
        instance = instances[instance_name]
        project_key = item.get("project_key")
        if instance.provider == "backlog":
            if not isinstance(project_key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", project_key):
                raise ConfigurationError(f"Backlog profile {name} requires project_key")
            project_key = project_key.upper()
        elif project_key is not None:
            raise ConfigurationError(f"Redmine profile {name} must not set project_key")
        markup = item.get("format", "backlog" if instance.provider == "backlog" else "textile")
        if markup not in {"backlog", "markdown", "textile"}:
            raise ConfigurationError(f"profile {name} has unsupported format")
        concurrency = item.get("concurrency", "best_effort")
        if concurrency not in {"best_effort", "strict"}:
            raise ConfigurationError(f"profile {name} has invalid concurrency")
        template = item.get("template")
        if template is not None and (
            not isinstance(template, str)
            or not re.fullmatch(r"[0-9a-f]{32}", template)
        ):
            raise ConfigurationError(f"profile {name} template must be an approved 32-character ID")
        allowlist_raw = item.get("write_allowlist", {})
        if not isinstance(allowlist_raw, dict):
            raise ConfigurationError(f"profile {name} write_allowlist must be a table")
        allowlist: dict[str, frozenset[str]] = {}
        for ticket, permissions in allowlist_raw.items():
            canonical = _canonical_literal(instance.provider, ticket)
            if canonical in allowlist:
                raise ConfigurationError(
                    f"profile {name} write_allowlist contains duplicate canonical ticket {canonical}"
                )
            if not isinstance(permissions, list) or not permissions:
                raise ConfigurationError(f"allowlist entry {ticket} must be a non-empty list")
            values = frozenset(permissions)
            if any(not isinstance(value, str) for value in permissions) or not values <= PERMISSIONS:
                raise ConfigurationError(f"allowlist entry {ticket} contains invalid permission")
            allowlist[canonical] = values
        profiles[name] = ProfileConfig(
            name=name,
            instance=instance,
            project_id=project_id,
            project_key=project_key,
            read_scope=read_scope,
            markup=markup,
            template=template,
            write_allowlist=allowlist,
            concurrency=concurrency,
        )
    return Config(path=path.resolve(), instances=instances, profiles=profiles)


def _canonical_literal(provider: str, ticket: object) -> str:
    if not isinstance(ticket, str):
        raise ConfigurationError("ticket allowlist key must be a string")
    value = ticket.strip()
    if provider == "backlog":
        if BACKLOG_KEY_RE.fullmatch(value):
            return value.upper()
        if REDMINE_ID_RE.fullmatch(value):
            return value
        raise ConfigurationError(f"invalid Backlog ticket ID: {ticket}")
    if not REDMINE_ID_RE.fullmatch(value):
        raise ConfigurationError(f"invalid Redmine ticket ID: {ticket}")
    return str(int(value))


def normalize_target(profile: ProfileConfig, raw_target: str) -> str:
    value = raw_target.strip()
    if "://" not in value:
        return _canonical_literal(profile.instance.provider, value)
    try:
        parsed = urlsplit(value)
        base = urlsplit(profile.instance.base_url)
        parsed_port = parsed.port or 443
        base_port = base.port or 443
    except ValueError as exc:
        raise IdentityError("ticket URL contains an invalid port or host") from exc
    if (
        parsed.scheme.lower() != base.scheme
        or parsed.hostname is None
        or parsed.hostname.lower() != base.hostname
        or parsed_port != base_port
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise IdentityError("ticket URL does not match the configured instance")
    base_path = base.path.rstrip("/")
    path = unquote(parsed.path)
    if base_path and path != base_path and not path.startswith(base_path + "/"):
        raise IdentityError("ticket URL is outside the configured Redmine subpath")
    relative = path[len(base_path) :] if base_path else path
    if profile.instance.provider == "backlog":
        match = re.fullmatch(r"/(?:view|api/v2/issues)/([^/]+)", relative)
    else:
        match = re.fullmatch(r"/issues/([1-9][0-9]*)(?:\.json)?", relative)
    if not match or "/" in match.group(1):
        raise IdentityError("unsupported ticket URL shape")
    return _canonical_literal(profile.instance.provider, match.group(1))


def canonical_identity(profile: ProfileConfig, canonical_ticket_id: str) -> TicketIdentity:
    return TicketIdentity(
        provider=profile.instance.provider,
        base_url=profile.instance.base_url,
        project_id=profile.project_id,
        ticket_id=_canonical_literal(profile.instance.provider, canonical_ticket_id),
    )


def permissions_for(
    profile: ProfileConfig,
    identity: TicketIdentity,
    aliases: tuple[str, ...] = (),
) -> frozenset[str]:
    expected = canonical_identity(profile, identity.ticket_id)
    if identity != expected:
        raise IdentityError("identity does not match the selected profile")
    granted = set(profile.write_allowlist.get(identity.ticket_id, frozenset()))
    for alias in aliases:
        canonical_alias = _canonical_literal(profile.instance.provider, alias)
        granted.update(profile.write_allowlist.get(canonical_alias, frozenset()))
    return frozenset(granted)


def require_permissions(
    profile: ProfileConfig,
    identity: TicketIdentity,
    required: set[str] | frozenset[str],
    aliases: tuple[str, ...] = (),
) -> None:
    if not required <= PERMISSIONS:
        raise PermissionDenied("operation requests unsupported permissions")
    granted = permissions_for(profile, identity, aliases)
    missing = sorted(required - granted)
    if missing:
        raise PermissionDenied(f"missing permissions: {', '.join(missing)}")
