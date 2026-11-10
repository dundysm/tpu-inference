#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Verify the release wheels on one TPU chip, before the publish block:
# serve_wheels.sh installs them into a fresh venv and runs serve_and_verify.sh
# with it, the same serve flow the staged image is checked with
# (verify_image_on_tpu.sh). Runs in the wheel carrier image that
# build_wheel_carrier_image.sh staged (python:3.12-slim with the wheels as
# plain files in /wheels). A step of tpu-inference-release-verify
# (verify_pipeline.yml), on the kube queue: the launcher
# (.buildkite/kubernetes/run.sh) starts the image as a TPU pod.
#
# Environment:
#   WHEEL_CARRIER_IMAGE_REF  The wheel carrier image, pinned by digest (set by
#                            the release build's trigger step).
#   VERIFY_MODEL             Model to serve (default:
#                            meta-llama/Llama-3.1-8B-Instruct).
#   VERIFY_NUM_PROMPTS       Requests in the bench (default: 30).
#   VERIFY_SERVER_TIMEOUT_S  How long to wait for /health (default: 3600).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

MODEL="${VERIFY_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
NUM_PROMPTS="${VERIFY_NUM_PROMPTS:-30}"
# The model download and the first TPU compile both happen before /health
# answers.
SERVER_TIMEOUT_S="${VERIFY_SERVER_TIMEOUT_S:-3600}"

IMAGE="${WHEEL_CARRIER_IMAGE_REF:-}"
[[ "${IMAGE}" == *@sha256:* ]] \
  || die "WHEEL_CARRIER_IMAGE_REF must name an image by digest, got '${IMAGE}'."
export WORKLOAD_IMAGE="${IMAGE}"

echo "--- :kubernetes: Verifying the wheels in $(digest_of "${IMAGE}") with ${MODEL} on ${SHAPE:-}"
# An absolute path into the image (build_wheel_carrier_image.sh), as CI's kube
# steps use: the launcher doesn't promise which directory the command starts
# in.
exec "${SCRIPT_DIR}/../kubernetes/run.sh" \
  env WHEELS_DIR=/wheels TEST_MODEL="${MODEL}" NUM_PROMPTS="${NUM_PROMPTS}" \
  SERVER_TIMEOUT_S="${SERVER_TIMEOUT_S}" \
  bash /workspace/release-verify/.buildkite/release/serve_wheels.sh
