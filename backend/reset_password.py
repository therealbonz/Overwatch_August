#!/usr/bin/env python3
"""
CLI utility to reset administrator passwords for therealbonz.com CMS & Launchpad.
Usage:
    python backend/reset_password.py [username] [new_password]
    python backend/reset_password.py --user admin --password "NoStress123!"
    python backend/reset_password.py (interactive prompt)
"""

import sys
import getpass
import argparse
from pathlib import Path

# Ensure backend directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from auth import reset_user_password, init_auth_data
except ImportError:
    from backend.auth import reset_user_password, init_auth_data


def main():
    parser = argparse.ArgumentParser(
        description="Reset administrator password for therealbonz.com CMS."
    )
    parser.add_argument("pos_username", nargs="?", default=None, help="Username to reset (e.g. admin or bonz)")
    parser.add_argument("pos_password", nargs="?", default=None, help="New password (min 6 chars)")
    parser.add_argument("-u", "--user", dest="flag_username", default=None, help="Username to reset")
    parser.add_argument("-p", "--password", dest="flag_password", default=None, help="New password")
    parser.add_argument("-r", "--role", dest="role", default=None, help="Role for user (superadmin or admin)")
    parser.add_argument("--test", action="store_true", help="Run automated self-test")

    args = parser.parse_args()

    if args.test:
        print("[RESET CLI] Running self-test...")
        test_user = reset_user_password("test_cli_user", "TestPassword123!", role="admin")
        assert test_user["username"] == "test_cli_user"
        # Clean up test user
        auth_data = init_auth_data()
        auth_data["users"] = [u for u in auth_data.get("users", []) if u["username"] != "test_cli_user"]
        from auth import save_auth_data
        save_auth_data(auth_data)
        print("[RESET CLI] Self-test passed successfully and cleaned up!")
        return

    username = args.pos_username or args.flag_username
    password = args.pos_password or args.flag_password

    if not username:
        default_user = "admin"
        try:
            val = input(f"Enter username to reset [{default_user}]: ").strip()
            username = val if val else default_user
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    username = username.strip()
    if not username:
        print("Error: Username cannot be empty.")
        sys.exit(1)

    if not password:
        try:
            # Use getpass if interactive tty, else standard input
            if sys.stdin.isatty():
                p1 = getpass.getpass("Enter new password (min 6 chars): ")
                p2 = getpass.getpass("Confirm new password: ")
                if p1 != p2:
                    print("Error: Passwords do not match.")
                    sys.exit(1)
                password = p1
            else:
                password = sys.stdin.readline().strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    password = password.strip()
    if len(password) < 6:
        print("Error: Password must be at least 6 characters long.")
        sys.exit(1)

    user = reset_user_password(username, password, role=args.role)
    print("=" * 60)
    print(f"✓ Success: Password reset for user '{user['username']}'")
    print(f"  Role: {user.get('role', 'admin')}")
    print(f"  Display Name: {user.get('display_name')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
