import os
import sys


def read_key(from_stdin=False):
    if from_stdin:
        # Never echo a credential through a terminal or save it to disk.
        if sys.stdin.isatty():
            import getpass
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass("Jev API key (hidden): ").strip()
        else:
            key = sys.stdin.readline().strip()

        if not key:
            raise ValueError("No key received on standard input")

        return key

    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key

    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment"
            ) as handle:
                key, _ = winreg.QueryValueEx(
                    handle, "TYPESAFE_API_KEY"
                )

            if key:
                return key

        except OSError:
            pass

    raise ValueError(
        "TYPESAFE_API_KEY is unavailable in this process "
        "or Windows user environment"
    )


if __name__ == "__main__":
    print("API key available:", bool(read_key()))