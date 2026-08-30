# syntax=docker/dockerfile:1
#
# Solana devnet build + deploy image — IRIS_BUILD_PROMPT v2.0 Phase 2 DoD.
#
# Phase 2's tests use solana-program-test with processor!(), which executes the
# real program against the real runtime without a validator or the SBF
# toolchain. That is enough to prove the custody gate, and it is *not* a
# deployment — the DoD also says the instructions work "on devnet".
#
# This image closes that gap. It carries the Solana CLI, which brings
# `cargo-build-sbf` and the platform-tools needed to produce a real BPF object,
# plus `solana program deploy`.
#
# Deliberately not installing anchor-cli. Deploying needs `cargo build-sbf` and
# `solana program deploy`, both of which ship with the Solana CLI; anchor-cli
# adds a ~30-minute cargo build to provide a wrapper around them. The IDL it
# would generate is not required for the deployment or for the gate.
#
# No keys are baked in. The deploy keypair lives in a mounted volume and never
# enters the image or the repository (v2.0 section 0c: zero private keys in
# source). It is a devnet key holding worthless SOL, and it still does not go
# in git.

FROM rust:1.90-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      pkg-config libssl-dev build-essential curl ca-certificates bzip2 jq git \
 && rm -rf /var/lib/apt/lists/*

ENV OPENSSL_NO_VENDOR=1
ENV CARGO_TERM_COLOR=always

# Pinned. An unpinned "stable" here would mean the bytecode this produces
# depends on the day it was built, which makes a deployed program impossible to
# reproduce from source.
# v4.2.2 rather than the 2.1.x line: platform-tools ships its own Rust for the
# BPF target, and 2.1.21's is 1.79 — too old for `edition2024`, which a
# transitive build-dependency of spl-token now requires. Pinning the dependency
# instead fights the resolver through four levels of the graph; the toolchain is
# the thing that is actually out of date.
ARG SOLANA_VERSION=4.2.2
RUN sh -c "$(curl -sSfL https://release.anza.xyz/v${SOLANA_VERSION}/install)"
ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"

RUN solana --version && cargo build-sbf --version

WORKDIR /work
COPY docker/devnet-deploy.sh /usr/local/bin/devnet-deploy
RUN chmod +x /usr/local/bin/devnet-deploy

CMD ["devnet-deploy"]
