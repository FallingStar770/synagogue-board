"""Command line: python -m app.cli <command>
  create-admin --username U --password P   create or reset an administrator
  seed-base                                 base data (prayer types, templates, default screens)
  seed-demo                                 demo content (clearly marked as samples)
  rebuild-snapshot                          force a new display snapshot
"""
import argparse
import getpass
import sys

from .db import SessionLocal
from .seed import create_admin, seed_base, seed_demo


def main(argv=None):
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin")
    a.add_argument("--username", required=True)
    a.add_argument("--password")
    a.add_argument("--display-name", default="מנהל")
    sub.add_parser("seed-base")
    sub.add_parser("seed-demo")
    sub.add_parser("rebuild-snapshot")
    args = p.parse_args(argv)
    with SessionLocal() as db:
        if args.cmd == "create-admin":
            pw = args.password or getpass.getpass("Password: ")
            u = create_admin(db, args.username, pw, args.display_name)
            print(f"admin ready: {u.username}")
        elif args.cmd == "seed-base":
            seed_base(db)
            print("base data ready")
        elif args.cmd == "seed-demo":
            seed_base(db)
            seed_demo(db)
            print("demo data ready")
        elif args.cmd == "rebuild-snapshot":
            from .services.snapshot import ensure_snapshot
            s = ensure_snapshot(db, force=True)
            print(f"snapshot v{s.version} ({s.size_bytes} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
