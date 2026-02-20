import argparse
import re
from datetime import timedelta
from agent import EmailAgent

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

DEFAULT_TIME_DELTA = timedelta(hours=1)


def _parse_time_delta(raw_value: str) -> timedelta:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd])\s*", raw_value.lower())
    if not match:
        raise argparse.ArgumentTypeError(
            "Invalid --time-delta value. Use format like 30m, 2h, or 1d."
        )

    amount = float(match.group(1))
    unit = match.group(2)
    if amount < 0:
        raise argparse.ArgumentTypeError("--time-delta must be non-negative.")

    unit_to_seconds = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }
    return timedelta(seconds=amount * unit_to_seconds[unit])


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review recent Gmail messages and notify important ones to Discord."
    )
    parser.add_argument(
        "--time-delta",
        type=_parse_time_delta,
        default=DEFAULT_TIME_DELTA,
        help="Only process emails received within this duration (e.g., 30m, 2h, 1d). Default: 2h.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    agent = EmailAgent()
    agent.run(time_delta=args.time_delta)


if __name__ == "__main__":
    main()
