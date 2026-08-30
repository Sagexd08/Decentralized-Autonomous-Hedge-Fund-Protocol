# syntax=docker/dockerfile:1
#
# Rust test runner for the Anchor programs.
#
# These tests use solana-program-test with processor!(), so they need neither a
# validator nor the SBF toolchain — but solana-runtime pulls in OpenSSL, whose
# vendored build does not work under Git Bash on Windows. Running them here
# keeps the security gate reproducible on every machine.
FROM rust:1.90-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      pkg-config libssl-dev build-essential \
 && rm -rf /var/lib/apt/lists/*

# system OpenSSL, so openssl-sys never reaches for its vendored copy
ENV OPENSSL_NO_VENDOR=1
ENV CARGO_TERM_COLOR=always

WORKDIR /work
CMD ["cargo", "test", "--workspace"]
