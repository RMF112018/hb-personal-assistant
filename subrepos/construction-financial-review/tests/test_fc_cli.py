"""CLI wiring: the forecast-comprehensive subcommand parses with the expected flags."""
from construction_financial_review.cli import build_parser


def test_subcommand_registered():
    args = build_parser().parse_args(["forecast-comprehensive", "--project", "tropical"])
    assert args.command == "forecast-comprehensive"
    assert args.project == "tropical"
    assert args.with_llm is False


def test_subcommand_flags():
    args = build_parser().parse_args([
        "forecast-comprehensive", "--project", "tropical",
        "--frozen-stamp", "20260101_000000", "--out-root", "/tmp/x", "--with-llm"])
    assert args.frozen_stamp == "20260101_000000"
    assert args.out_root == "/tmp/x"
    assert args.with_llm is True
