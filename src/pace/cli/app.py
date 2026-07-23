"""Minimal CLI entry point for the Pace application."""

from argparse import ArgumentParser


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="pace",
        description="A private, local-first endurance coaching system.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="pace 0.1.0",
    )
    return parser


def main() -> None:
    build_parser().parse_args()
