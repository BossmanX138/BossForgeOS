def _run(args):
    print(f"Forge Echo: {args.message}")


def register(subparsers):
    parser = subparsers.add_parser("forge-echo", help="Example plugin command")
    parser.add_argument("message")
    parser.set_defaults(func=_run)
