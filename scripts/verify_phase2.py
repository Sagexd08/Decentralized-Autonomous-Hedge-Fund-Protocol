#!/usr/bin/env python3
"""
Phase 2 gate check — IRIS_BUILD_PROMPT v2.0 section 27.

Definition of Done:
    Register/stake/unstake work on devnet; **agent-cannot-withdraw-vault test
    passes**.

The second clause is the one section 5 calls "the single highest-priority
security test in the whole repo", so this script does not merely check that
`cargo test` exited 0 — a suite that silently stopped running the custody tests
would do that too. It asserts each required test ran *and* passed by name.

    python scripts/verify_phase2.py

Exit code 0 means the security gate is met.
"""

from __future__ import annotations

import re
import subprocess
import sys

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m",
)

# The custody boundary. Every one of these must pass by name.
CUSTODY_TESTS = [
    "agent_pda_cannot_sign_a_vault_withdrawal",
    "a_signing_agent_cannot_drain_a_depositors_balance",
    "an_agent_cannot_conjure_its_own_balance_account",
    "an_agent_cannot_impersonate_the_allocation_engine",
    # the control: the guards must be about authority, not a broken path
    "the_depositor_can_still_withdraw",
]

# register / stake / unstake, per the first clause of the DoD.
LIFECYCLE_TESTS = [
    "register_agent_records_identity_and_moves_the_stake",
    "registering_below_the_minimum_stake_is_rejected",
    "stake_and_unstake_move_collateral_both_ways",
    "a_live_agent_cannot_unstake_below_the_minimum",
    "a_stranger_cannot_stake_against_someone_elses_agent",
    "update_model_bumps_the_version",
    "republishing_the_same_model_is_rejected",
    "a_stranger_cannot_swap_an_agents_model",
    "freeze_is_reversible_and_zeroes_allocation",
    "deactivation_retires_the_agent_and_zeroes_allocation",
    "a_retired_agent_may_recover_its_full_stake",
    "only_the_admin_may_freeze_an_agent",
]

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_suite() -> str:
    """Run the Anchor tests in the Linux container and return clean output."""
    print(f"{DIM}building the test image…{RESET}")
    build = subprocess.run(
        ["docker", "build", "-f", "docker/anchor.Dockerfile", "-t", "iris-anchor-test", "."],
        capture_output=True, text=True,
    )
    if build.returncode != 0:
        print(f"{RED}FAIL{RESET}  could not build the test image:\n{build.stderr[-2000:]}")
        sys.exit(2)

    print(f"{DIM}running cargo test --workspace…{RESET}\n")
    proc = subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", "//c/Desktop/Coding/hacktropica/programs/iris:/work",
            "-v", "iris-cargo-registry:/usr/local/cargo/registry",
            "-v", "iris-cargo-target:/work/target",
            "iris-anchor-test", "cargo", "test", "--workspace",
        ],
        capture_output=True, text=True,
    )
    return ANSI.sub("", proc.stdout + proc.stderr)


def check(output: str, names: list[str], heading: str) -> bool:
    print(f"{heading}")
    ok = True
    for name in names:
        if re.search(rf"^test {re.escape(name)} \.\.\. ok$", output, re.M):
            print(f"  {GREEN}PASS{RESET}  {name}")
        elif re.search(rf"^test {re.escape(name)} \.\.\.", output, re.M):
            print(f"  {RED}FAIL{RESET}  {name}")
            ok = False
        else:
            print(f"  {RED}MISS{RESET}  {name} {DIM}(did not run){RESET}")
            ok = False
    print()
    return ok


def main() -> int:
    output = run_suite()

    custody = check(output, CUSTODY_TESTS, "Custody boundary — agents never hold capital")
    lifecycle = check(output, LIFECYCLE_TESTS, "Registry lifecycle — register / stake / unstake")

    if not (custody and lifecycle):
        print(f"{RED}Phase 2 gate FAILED{RESET} — do not checkpoint.\n")
        return 1

    print(f"{GREEN}Phase 2 security gate PASSED{RESET} — "
          f"{len(CUSTODY_TESTS) + len(LIFECYCLE_TESTS)} tests green.")
    print(
        f"\n{YELLOW}Not covered by this gate:{RESET} the DoD also says these "
        f"instructions work\n\"on devnet\". Deploying needs the solana and anchor "
        f"CLIs plus a funded\ndevnet keypair, none of which are available here. "
        f"These tests run against\nsolana-program-test, which executes the real "
        f"program against the real runtime\nbut is not the same as a deployment. "
        f"Treat devnet as outstanding.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
