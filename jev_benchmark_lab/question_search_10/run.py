"""Run the bounded ten-iteration search."""
import argparse

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    args = parser.parse_args()
    if args.command == "prepare":
        from .data_sets import prepare
        return prepare()
    if args.command == "test":
        import unittest
        from . import test_search
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_search))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if args.command in ("iterate", "final"):
        from . import search
        return getattr(search, args.command)()
    if args.command in ("report", "verify", "status"):
        from . import reporting
        return getattr(reporting, args.command)()
    raise SystemExit("Unknown command: " + args.command)

if __name__ == "__main__":
    main()
