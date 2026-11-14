#!/bin/bash
# Build the NAM C++ terrain cruncher as a shared library for ctypes.
# Produces libterrain.so (Linux) / libterrain.dylib (macOS).
set -e
cd "$(dirname "$0")"
EXT=so; FLAGS="-fPIC -shared"
case "$(uname -s)" in Darwin) EXT=dylib;; esac
g++ -O3 $FLAGS terrain.cpp -o libterrain.$EXT
echo "built libterrain.$EXT ($(du -h libterrain.$EXT | cut -f1))"
./probe 2>/dev/null || true
