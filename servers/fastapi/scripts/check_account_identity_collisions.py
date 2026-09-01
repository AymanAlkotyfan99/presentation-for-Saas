"""Read-only, privacy-safe account identifier collision preflight.

This migration shadow command deliberately owns no runtime login or
registration behavior. Its normalization fixtures must stay aligned with the
canonical identity normalizer introduced by the later lifecycle foundation.
Output contains only finite categories, counts, and canonical UUIDs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import os
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid5

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import create_engine, inspect, text

from utils.db_utils import to_sync_sqlalchemy_url


@dataclass(frozen=True, order=True)
class IdentityCandidate:
    normalized_value: str
    kind: str
    subject_id: str
    owner_key: str


def normalize_username(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def normalize_candidate_email(value: str) -> str:
    display = unicodedata.normalize("NFC", value.strip())
    if any(unicodedata.category(character).startswith("C") for character in display):
        raise ValueError("control_character")
    try:
        validated = validate_email(display, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError("invalid_email") from exc
    domain = validated.ascii_domain or validated.domain.encode("idna").decode("ascii")
    return f"{validated.local_part}@{domain}".casefold()


def _safe_subject_id(source: str, raw_id: object) -> str:
    try:
        return str(UUID(str(raw_id)))
    except ValueError:
        return str(uuid5(NAMESPACE_URL, f"bayanly-preflight:{source}:{raw_id}"))


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _collect_candidates(connection) -> tuple[list[IdentityCandidate], list[str]]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    candidates: list[IdentityCandidate] = []
    invalid_ids: list[str] = []

    if "user" in tables:
        columns = _columns(inspector, "user")
        selected = ["id"]
        selected.extend(
            column
            for column in ("username", "email_original", "email_normalized")
            if column in columns
        )
        rows = connection.execute(
            text(f'SELECT {", ".join(selected)} FROM "user" ORDER BY id')
        ).mappings()
        for row in rows:
            subject_id = _safe_subject_id("user", row["id"])
            owner_key = f"user:{subject_id}"
            username = row.get("username")
            if username:
                normalized = normalize_username(username)
                if normalized:
                    candidates.append(
                        IdentityCandidate(
                            normalized, "USERNAME", subject_id, owner_key
                        )
                    )
            email = row.get("email_original") or row.get("email_normalized")
            if email:
                try:
                    normalized = normalize_candidate_email(email)
                except ValueError:
                    invalid_ids.append(subject_id)
                else:
                    candidates.append(
                        IdentityCandidate(normalized, "EMAIL", subject_id, owner_key)
                    )

    if "account_pending_registrations" in tables:
        columns = _columns(inspector, "account_pending_registrations")
        if "id" in columns and (
            "email_original" in columns or "email_normalized" in columns
        ):
            selected = ["id"]
            selected.extend(
                column
                for column in ("email_original", "email_normalized")
                if column in columns
            )
            rows = connection.execute(
                text(
                    "SELECT "
                    f"{', '.join(selected)} "
                    "FROM account_pending_registrations ORDER BY id"
                )
            ).mappings()
            for row in rows:
                email = row.get("email_original") or row.get("email_normalized")
                if not email:
                    continue
                subject_id = _safe_subject_id("pending", row["id"])
                try:
                    normalized = normalize_candidate_email(email)
                except ValueError:
                    invalid_ids.append(subject_id)
                else:
                    candidates.append(
                        IdentityCandidate(
                            normalized,
                            "EMAIL",
                            subject_id,
                            f"pending:{subject_id}",
                        )
                    )

    # Existing registry rows are included so a partially deployed expand
    # schema is checked without trusting its stored comparison value alone.
    if "account_login_identifiers" in tables:
        columns = _columns(inspector, "account_login_identifiers")
        required = {
            "normalized_value",
            "kind",
            "user_id",
            "pending_registration_id",
        }
        if required.issubset(columns):
            rows = connection.execute(
                text(
                    """
                    SELECT normalized_value, kind, user_id, pending_registration_id
                    FROM account_login_identifiers
                    ORDER BY normalized_value
                    """
                )
            ).mappings()
            for row in rows:
                raw_owner = row["user_id"] or row["pending_registration_id"]
                if raw_owner is None:
                    continue
                source = "user" if row["user_id"] is not None else "pending"
                subject_id = _safe_subject_id(source, raw_owner)
                kind = row["kind"]
                try:
                    normalized = (
                        normalize_candidate_email(row["normalized_value"])
                        if kind == "EMAIL"
                        else normalize_username(row["normalized_value"])
                    )
                except ValueError:
                    invalid_ids.append(subject_id)
                    continue
                candidates.append(
                    IdentityCandidate(
                        normalized, kind, subject_id, f"{source}:{subject_id}"
                    )
                )

    return sorted(set(candidates)), sorted(set(invalid_ids))


def build_report(database_url: str) -> dict[str, object]:
    engine = create_engine(to_sync_sqlalchemy_url(database_url))
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                if connection.dialect.name == "postgresql":
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                elif connection.dialect.name == "sqlite":
                    connection.execute(text("PRAGMA query_only=ON"))
                candidates, invalid_ids = _collect_candidates(connection)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    grouped: dict[str, list[IdentityCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.normalized_value].append(candidate)

    category_ids: dict[str, set[str]] = defaultdict(set)
    category_groups: dict[str, int] = defaultdict(int)
    for group in grouped.values():
        owners = {candidate.owner_key for candidate in group}
        if len(owners) < 2:
            continue
        kinds = {candidate.kind for candidate in group}
        if kinds == {"USERNAME"}:
            category = "USERNAME_USERNAME"
        elif kinds == {"EMAIL"}:
            category = "EMAIL_EMAIL"
        else:
            category = "EMAIL_USERNAME_ALIAS"
        category_groups[category] += 1
        category_ids[category].update(candidate.subject_id for candidate in group)
    if invalid_ids:
        category_groups["INVALID_EMAIL"] = len(invalid_ids)
        category_ids["INVALID_EMAIL"].update(invalid_ids)

    categories = [
        {
            "category": category,
            "count": len(category_ids[category]),
            "collision_groups": category_groups[category],
            "subject_ids": sorted(category_ids[category]),
        }
        for category in sorted(category_ids)
    ]
    total_collisions = sum(category_groups.values())
    return {
        "categories": categories,
        "status": "ambiguous" if total_collisions else "clean",
        "total_collisions": total_collisions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check account identifier collisions without disclosing identities"
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    try:
        report = build_report(args.database_url)
    except Exception:
        # Connection/provider exception text can contain credentials or raw
        # identifiers. Operators get a stable failure category only.
        report = {
            "categories": [
                {
                    "category": "PREFLIGHT_FAILED",
                    "count": 0,
                    "collision_groups": 0,
                    "subject_ids": [],
                }
            ],
            "status": "error",
            "total_collisions": 0,
        }
    if args.format == "json":
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(f"status={report['status']} total_collisions={report['total_collisions']}")
        for category in report["categories"]:
            print(
                f"category={category['category']} count={category['count']} "
                f"collision_groups={category['collision_groups']} "
                f"subject_ids={','.join(category['subject_ids'])}"
            )
    if report["status"] == "clean":
        return 0
    return 3 if report["status"] == "error" else 2


if __name__ == "__main__":
    raise SystemExit(main())
