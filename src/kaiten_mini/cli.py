"""kaiten CLI entrypoint: argparse subcommands over KaitenClient."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx

from kaiten_mini.client import DEFAULT_BASE_DOMAIN, KaitenApiError, KaitenClient, build_base_url
from kaiten_mini.output import fail, print_json


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def make_client(args: argparse.Namespace) -> KaitenClient:
    token = args.token or _env("KAITEN_TOKEN")
    if not token:
        raise ValueError("Kaiten token is not configured: pass --token or set KAITEN_TOKEN")
    base_url = build_base_url(
        subdomain=args.subdomain or _env("KAITEN_SUBDOMAIN") or _env("KAITEN_DOMAIN"),
        base_domain=args.base_domain or _env("KAITEN_BASE_DOMAIN") or DEFAULT_BASE_DOMAIN,
        base_url=args.base_url or _env("KAITEN_BASE_URL"),
    )
    return KaitenClient(base_url=base_url, token=token)


# --- command handlers: (client, args) -> JSON-serializable data ---


def cmd_whoami(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get("/users/current")


def cmd_spaces_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get("/spaces")


def cmd_boards_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get(f"/spaces/{args.space}/boards")


def cmd_columns_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get(f"/boards/{args.board}/columns")


def cmd_users_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    params = {"query": args.query, "limit": args.limit, "offset": args.offset}
    if args.include_inactive:
        params["include_inactive"] = "true"
    return client.get("/users", params=params)


def cmd_users_get(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get(f"/users/{args.user_id}")


def cmd_cards_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    params = {
        "board_id": args.board,
        "space_id": args.space,
        "column_id": args.column,
        "query": args.query,
        "owner_id": args.owner,
        "responsible_id": args.responsible,
        "member_ids": args.member,
        "states": args.state,
        "limit": args.limit,
        "offset": args.offset,
    }
    return client.get("/cards", params=params)


def cmd_cards_get(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get(f"/cards/{args.card_id}")


def cmd_cards_create(client: KaitenClient, args: argparse.Namespace) -> Any:
    body: dict[str, Any] = {"title": args.title, "board_id": args.board}
    for key, attr in (
        ("column_id", "column"),
        ("lane_id", "lane"),
        ("description", "description"),
        ("due_date", "due"),
        ("owner_id", "owner"),
        ("responsible_id", "responsible"),
        ("type_id", "type"),
    ):
        value = getattr(args, attr)
        if value is not None:
            body[key] = value
    if args.asap:
        body["asap"] = True
    return client.post("/cards", body)


def cmd_cards_update(client: KaitenClient, args: argparse.Namespace) -> Any:
    body: dict[str, Any] = {}
    for key, attr in (
        ("title", "title"),
        ("description", "description"),
        ("due_date", "due"),
        ("owner_id", "owner"),
        ("responsible_id", "responsible"),
        ("type_id", "type"),
    ):
        value = getattr(args, attr)
        if value is not None:
            body[key] = value
    if args.asap:
        body["asap"] = True
    if args.archive:
        body["condition"] = 2
    if not body:
        raise ValueError("nothing to update: pass at least one of --title/--description/--due/...")
    return client.patch(f"/cards/{args.card_id}", body)


def cmd_cards_move(client: KaitenClient, args: argparse.Namespace) -> Any:
    body: dict[str, Any] = {"column_id": args.column}
    if args.lane is not None:
        body["lane_id"] = args.lane
    if args.board is not None:
        body["board_id"] = args.board
    return client.patch(f"/cards/{args.card_id}", body)


def cmd_comments_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.get(f"/cards/{args.card_id}/comments")


def cmd_comments_add(client: KaitenClient, args: argparse.Namespace) -> Any:
    return client.post(f"/cards/{args.card_id}/comments", {"text": args.text})


def cmd_time_logs_list(client: KaitenClient, args: argparse.Namespace) -> Any:
    params = {"for_date": args.for_date}
    if args.personal:
        params["personal"] = "true"
    return client.get(f"/cards/{args.card}/time-logs", params=params)


def cmd_time_logs_add(client: KaitenClient, args: argparse.Namespace) -> Any:
    body: dict[str, Any] = {"time_spent": args.minutes, "role_id": args.role_id}
    if args.for_date is not None:
        body["for_date"] = args.for_date
    if args.comment is not None:
        body["comment"] = args.comment
    return client.post(f"/cards/{args.card}/time-logs", body)


def _parse_param(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        raise ValueError(f"--param expects key=value, got: {raw!r}")
    key, value = raw.split("=", 1)
    if not key:
        raise ValueError(f"--param expects key=value, got: {raw!r}")
    if value.lower() in ("true", "false"):
        return key, value.lower() == "true"
    try:
        return key, int(value)
    except ValueError:
        return key, value


def cmd_api(client: KaitenClient, args: argparse.Namespace) -> Any:
    """Raw escape hatch: any endpoint, no dedicated command needed."""
    method = args.method.upper()
    path = args.path if args.path.startswith("/") else "/" + args.path
    params = dict(_parse_param(p) for p in args.param)
    body = None
    if args.body is not None:
        raw = args.body
        if raw.startswith("@"):
            with open(raw[1:], encoding="utf-8") as f:
                raw = f.read()
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"--body must be JSON or @file: {e}") from e
    if method == "GET":
        return client.get(path, params=params or None)
    if method in ("POST", "PATCH", "PUT"):
        if body is None:
            raise ValueError(f"{method} requires --body")
        return {"POST": client.post, "PATCH": client.patch, "PUT": client.put}[method](path, body)
    if method == "DELETE":
        return client.delete(path)
    raise ValueError(f"unsupported method {method!r}: use GET/POST/PATCH/PUT/DELETE")


# --- parser ---


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--subdomain", help="Kaiten subdomain (env KAITEN_SUBDOMAIN)")
    common.add_argument("--token", help="API token (env KAITEN_TOKEN)")
    common.add_argument("--base-url", help="Full API host override (env KAITEN_BASE_URL)")
    common.add_argument("--base-domain", help=f"Base domain (default {DEFAULT_BASE_DOMAIN})")
    common.add_argument("--fields", help="Keep only these top-level fields, comma-separated")
    common.add_argument("--compact", action="store_true", help="Single-line JSON output")

    parser = argparse.ArgumentParser(
        prog="kaiten-mini",
        description="Small CLI over the Kaiten REST API. Output is always JSON on stdout; "
        "errors are JSON on stderr with exit code 1.",
    )
    groups = parser.add_subparsers(dest="group", required=True, metavar="GROUP")

    def leaf(group_parser: argparse._SubParsersAction, name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = group_parser.add_parser(name, parents=[common], help=help_text, description=help_text)
        p.set_defaults(func=func)
        return p

    leaf(groups, "whoami", cmd_whoami, "Current user (auth check)")

    p = leaf(groups, "api", cmd_api, "Raw call to any API endpoint (escape hatch)")
    p.add_argument("method", help="HTTP method: GET/POST/PATCH/PUT/DELETE")
    p.add_argument("path", help="API path relative to /api/latest, e.g. /cards/123 or cards")
    p.add_argument("--param", action="append", default=[], help="Query param key=value (repeatable; values auto-typed to int/bool)")
    p.add_argument("--body", help="JSON body or @file.json (required for POST/PATCH/PUT)")

    spaces = groups.add_parser("spaces", help="Spaces").add_subparsers(dest="action", required=True, metavar="ACTION")
    leaf(spaces, "list", cmd_spaces_list, "List spaces")

    boards = groups.add_parser("boards", help="Boards").add_subparsers(dest="action", required=True, metavar="ACTION")
    p = leaf(boards, "list", cmd_boards_list, "List boards of a space")
    p.add_argument("--space", type=int, required=True, help="Space ID")

    columns = groups.add_parser("columns", help="Board columns").add_subparsers(dest="action", required=True, metavar="ACTION")
    p = leaf(columns, "list", cmd_columns_list, "List columns of a board")
    p.add_argument("--board", type=int, required=True, help="Board ID")

    users = groups.add_parser("users", help="Company users").add_subparsers(dest="action", required=True, metavar="ACTION")

    p = leaf(users, "list", cmd_users_list, "List/search company users")
    p.add_argument("--query", help="Search by name or email")
    p.add_argument("--include-inactive", action="store_true", help="Include deactivated users")
    p.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    p.add_argument("--offset", type=int, help="Pagination offset")

    p = leaf(users, "get", cmd_users_get, "Get a user by ID")
    p.add_argument("user_id", type=int, help="User ID")

    cards = groups.add_parser("cards", help="Cards").add_subparsers(dest="action", required=True, metavar="ACTION")

    p = leaf(cards, "list", cmd_cards_list, "Search/list cards (conditions: 1=active, 2=archived)")
    p.add_argument("--board", type=int, help="Board ID")
    p.add_argument("--space", type=int, help="Space ID")
    p.add_argument("--column", type=int, help="Column ID")
    p.add_argument("--query", help="Full-text search")
    p.add_argument("--owner", type=int, help="Owner user ID (see: whoami)")
    p.add_argument("--responsible", type=int, help="Responsible user ID")
    p.add_argument("--member", help="Member user ID (cards where user is a member)")
    p.add_argument("--state", help="Comma-separated states: 1=queued,2=inProgress,3=done")
    p.add_argument("--limit", type=int, default=30, help="Max results (default 30, max 100)")
    p.add_argument("--offset", type=int, help="Pagination offset")

    p = leaf(cards, "get", cmd_cards_get, "Get a card by ID or key (e.g. PROJ-123)")
    p.add_argument("card_id", help="Card ID or key")

    p = leaf(cards, "create", cmd_cards_create, "Create a card")
    p.add_argument("--board", type=int, required=True, help="Target board ID")
    p.add_argument("--title", required=True, help="Card title (1-1024 chars)")
    p.add_argument("--column", type=int, help="Target column ID")
    p.add_argument("--lane", type=int, help="Target lane ID")
    p.add_argument("--description", help="Description (max 32768 chars)")
    p.add_argument("--due", help="Deadline, ISO 8601 (YYYY-MM-DD)")
    p.add_argument("--owner", type=int, help="Owner user ID")
    p.add_argument("--responsible", type=int, help="Responsible user ID")
    p.add_argument("--type", type=int, help="Card type ID")
    p.add_argument("--asap", action="store_true", help="ASAP marker")

    p = leaf(cards, "update", cmd_cards_update, "Update card fields")
    p.add_argument("card_id", help="Card ID or key")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--due", help="New deadline, ISO 8601")
    p.add_argument("--owner", type=int, help="Owner user ID")
    p.add_argument("--responsible", type=int, help="Responsible user ID")
    p.add_argument("--type", type=int, help="Card type ID")
    p.add_argument("--asap", action="store_true")
    p.add_argument("--archive", action="store_true", help="Archive the card (condition=2)")

    p = leaf(cards, "move", cmd_cards_move, "Move a card to another column/lane/board")
    p.add_argument("card_id", help="Card ID or key")
    p.add_argument("--column", type=int, required=True, help="Target column ID (see: columns list)")
    p.add_argument("--lane", type=int, help="Target lane ID")
    p.add_argument("--board", type=int, help="Target board ID (when moving across boards)")

    comments = groups.add_parser("comments", help="Card comments").add_subparsers(dest="action", required=True, metavar="ACTION")

    p = leaf(comments, "list", cmd_comments_list, "List comments of a card")
    p.add_argument("card_id", type=int, help="Card ID")

    p = leaf(comments, "add", cmd_comments_add, "Add a comment to a card")
    p.add_argument("card_id", type=int, help="Card ID")
    p.add_argument("--text", required=True, help="Comment text (markdown)")

    time_logs = groups.add_parser("time-logs", help="Time logs").add_subparsers(dest="action", required=True, metavar="ACTION")

    p = leaf(time_logs, "list", cmd_time_logs_list, "List time logs of a card")
    p.add_argument("--card", type=int, required=True, help="Card ID")
    p.add_argument("--for-date", help="Filter by date (YYYY-MM-DD)")
    p.add_argument("--personal", action="store_true", help="Only the current user's logs")

    p = leaf(time_logs, "add", cmd_time_logs_add, "Log time spent on a card")
    p.add_argument("--card", type=int, required=True, help="Card ID")
    p.add_argument("--minutes", type=int, required=True, help="Time spent in minutes (>= 1)")
    p.add_argument("--for-date", help="Date of the log (YYYY-MM-DD), default today")
    p.add_argument("--comment", help="Comment for the log entry")
    p.add_argument("--role-id", type=int, default=-1, help="Role ID (default -1 = default role)")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        client = make_client(args)
    except ValueError as e:
        fail(str(e))
    try:
        result = args.func(client, args)
    except KaitenApiError as e:
        fail(e.message, status=e.status_code)
    except httpx.HTTPError as e:
        fail(f"network error: {e}")
    except ValueError as e:
        fail(str(e))
    finally:
        client.close()
    print_json(result, fields=args.fields, compact=args.compact)


if __name__ == "__main__":
    main()
