# Fat Debian-based Rust image.
# Includes the ~35 -dev packages that (per docs/cargo/survey-findings.md)
# cover ~93% of real-world Rust projects that consume native C libraries
# via *-sys crates.
#
# Build:  docker build --build-arg RUST_VERSION=1.92 -t rp2026/cargo-fat:1.92 docker/cargo-fat
# Tag:    rp2026/cargo-fat:<rust-minor>
ARG RUST_VERSION=1.75
FROM rust:${RUST_VERSION}-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Core build tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    pkg-config \
    build-essential \
    cmake \
    clang \
    libclang-dev \
 && rm -rf /var/lib/apt/lists/*

# Common native library -dev packages that show up in *-sys dependencies.
# Grouped thematically; grouping is cosmetic, apt resolves everything in one pass.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # crypto / TLS / networking
    libssl-dev \
    libcurl4-openssl-dev \
    libssh2-1-dev \
    libnghttp2-dev \
    # databases
    libsqlite3-dev \
    libpq-dev \
    librocksdb-dev \
    # compression
    zlib1g-dev \
    libzstd-dev \
    libbz2-dev \
    liblzma-dev \
    liblz4-dev \
    # text / regex
    libonig-dev \
    # packet capture / raw net
    libpcap-dev \
    # audio / hardware / ipc
    libasound2-dev \
    libudev-dev \
    libdbus-1-dev \
    # vcs
    libgit2-dev \
    # misc
    libexpat1-dev \
    libxml2-dev \
 && rm -rf /var/lib/apt/lists/*

# GUI stack (GTK3 + WebKit) — needed for Tauri-based projects such as
# the netscli test case. Big (~500 MB), which is the main cost of the fat
# image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-dev \
    libglib2.0-dev \
    libgdk-pixbuf2.0-dev \
    libpango1.0-dev \
    libcairo2-dev \
    libatk1.0-dev \
    libsoup-3.0-dev \
    libwebkit2gtk-4.1-dev \
    libayatana-appindicator3-dev \
    # windowing backends
    libwayland-dev \
    libegl-dev \
    libgl-dev \
 && rm -rf /var/lib/apt/lists/*

# Sanity check
RUN cargo --version && rustc --version && pkg-config --version

CMD ["cargo", "--version"]
