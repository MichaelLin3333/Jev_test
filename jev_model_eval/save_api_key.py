import getpass
import os
import winreg

key = getpass.getpass("Enter your TypeSafe API key: ").strip()

if not key:
    raise ValueError("No API key entered.")

# Available to this Python process immediately.
os.environ["TYPESAFE_API_KEY"] = key

# Persistently saved in Windows user environment settings.
with winreg.CreateKey(
    winreg.HKEY_CURRENT_USER, "Environment"
) as registry:
    winreg.SetValueEx(
        registry,
        "TYPESAFE_API_KEY",
        0,
        winreg.REG_SZ,
        key,
    )

print("API key saved in Windows user environment settings.")