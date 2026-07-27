from __future__ import annotations

from app.integrations.google_calendar import run_authorization_flow


def main() -> None:
    token_file = run_authorization_flow()
    print(f"Created {token_file.resolve()}")


if __name__ == "__main__":
    main()
