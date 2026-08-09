"""Command-line management for the NayDoeV1 orchestration service."""

import argparse
import json
import os
from typing import List, Optional

from orchestration.service import OrchestrationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orcai-orchestrator",
        description="Manage the NayDoeV1 VPS orchestration service",
    )
    parser.add_argument(
        "--database",
        help="SQLite database path (or use ORCAI_DATABASE_PATH)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser(
        "init",
        help="Create a tenant, NayDoeV1 identity, and first API key",
    )
    initialize.add_argument("--tenant-name", required=True)
    initialize.add_argument("--tenant-slug", default="naydoev1")

    create_key = subparsers.add_parser(
        "create-key",
        help="Create another API key and print it once",
    )
    create_key.add_argument("--tenant-slug", default="naydoev1")
    create_key.add_argument("--name", required=True)
    create_key.add_argument(
        "--scopes",
        default="read",
        help="Comma-separated scopes",
    )

    profile = subparsers.add_parser(
        "profile",
        help="Print the registered NayDoeV1 profile",
    )
    profile.add_argument("--tenant-slug", default="naydoev1")

    serve = subparsers.add_parser("serve", help="Run the SaaS HTTP server")
    serve.add_argument(
        "--host",
        default=os.environ.get("ORCAI_HOST", "127.0.0.1"),
    )
    serve.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ORCAI_PORT", "8080")),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    service = OrchestrationService(database_path=args.database)

    if args.command == "init":
        result = service.bootstrap(args.tenant_name, args.tenant_slug)
        print(
            json.dumps(
                {
                    "tenant": result["tenant"],
                    "naydoev1": {
                        "model_number": result["identity"]["model_number"],
                        "serial_number": result["identity"]["serial_number"],
                        "registration_hash": result["identity"][
                            "registration_hash"
                        ],
                    },
                    "api_key": result["api_key"]["api_key"],
                    "warning": (
                        "Store this API key now. Only its scrypt hash is "
                        "persisted and the plaintext cannot be recovered."
                    ),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "create-key":
        tenant = service.database.get_tenant_by_slug(args.tenant_slug)
        if not tenant:
            raise SystemExit("Tenant not found")
        key = service.create_api_key(
            tenant["id"],
            args.name,
            [
                scope.strip()
                for scope in args.scopes.split(",")
                if scope.strip()
            ],
        )
        print(
            json.dumps(
                {
                    "api_key": key["api_key"],
                    "scopes": key["scopes"],
                    "warning": "This plaintext key is shown only once.",
                },
                indent=2,
            )
        )
        return 0

    if args.command == "profile":
        profile_data = service.public_naydoev1_profile(args.tenant_slug)
        if not profile_data:
            raise SystemExit("NayDoeV1 is not registered for that tenant")
        print(json.dumps(profile_data, indent=2))
        return 0

    if args.command == "serve":
        if not 1024 <= args.port <= 65535:
            raise SystemExit("Port must be between 1024 and 65535")
        import uvicorn

        from orchestration.api import create_app

        uvicorn.run(
            create_app(service),
            host=args.host,
            port=args.port,
            proxy_headers=True,
            forwarded_allow_ips=os.environ.get(
                "ORCAI_FORWARDED_ALLOW_IPS",
                "127.0.0.1",
            ),
            access_log=True,
        )
        return 0

    return 1
