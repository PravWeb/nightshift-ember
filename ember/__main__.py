"""Ember CLI.

    python3 -m ember register   register with the bridge, persist the key
    python3 -m ember run        register if needed, then work the room
    python3 -m ember simulate   offline demo transcript (no server needed)
"""

from __future__ import annotations

import argparse
import sys

from .agent import EmberAgent
from .client import SwitchClient
from .config import Config, load_dotenv
from .simulate import run_simulation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ember", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="register and persist the API key")
    reg.add_argument("--overwrite", action="store_true",
                     help="re-register even if the name already exists")
    sub.add_parser("run", help="run the agent against the bridge")
    sub.add_parser("simulate", help="offline transcript against a fake bridge")
    args = parser.parse_args(argv)

    load_dotenv()
    config = Config.from_env()

    if args.command == "simulate":
        print(run_simulation(config))
        return 0

    client = SwitchClient(config)
    if args.command == "register":
        if client.registered and not args.overwrite:
            print(f"already registered as {client.agent_id} "
                  f"(state: {config.state_path}); use --overwrite to redo")
            return 0
        result = client.register(overwrite=args.overwrite)
        print(f"registered: agent id {result['id']} "
              f"(API key persisted to {config.state_path}, shown only once)")
        return 0

    if args.command == "run":
        agent = EmberAgent(config, client)
        try:
            agent.run_forever()
        except KeyboardInterrupt:
            print("\n[ember] interrupted; shutting down", file=sys.stderr)
            agent.stop()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
