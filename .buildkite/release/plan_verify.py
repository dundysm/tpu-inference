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
"""Print the TPU check and the publish-planning step of a release build as a
Buildkite pipeline (JSON).

    plan_verify.py | buildkite-agent pipeline upload --no-interpolation

Runs once the image and the wheel carrier image are staged. The TPU check is a
trigger step: it starts tpu-inference-release-verify (verify_pipeline.yml) on
the TPU CI cluster, on this build's commit, and waits for it. That cluster has
the TPU fleet; this one has the release credentials, and none of them go along:
the triggered build only gets the two image references, pinned by digest.
Generated rather than static because the digests exist only at run time.
plan_publish, which uploads the approval block, waits for the check.

Optional build env:
  RELEASE_VERIFY_PIPELINE=<slug>  pipeline to trigger (default:
                                  tpu-inference-release-verify)
  RELEASE_VERIFY_SKIP=<reason>    skip the TPU check; an annotation records
                                  the reason
  RELEASE_QUEUE=<queue>           agent queue (default: release-tpu-inference)
"""

import json
import os
import subprocess
import sys

from plan_publish import QUEUE, meta

PLAN_PUBLISH_CMD = ("python3 .buildkite/release/plan_publish.py"
                    " | buildkite-agent pipeline upload --no-interpolation")


def pinned(key):
    """The image reference in meta-data <key>, which must be by digest."""
    ref = meta(key)
    if "@sha256:" not in ref:
        sys.exit(f"ERROR: meta-data {key} is '{ref}', not an image digest.")
    return ref


def main():
    version = meta("release-version")
    staged = pinned("release-image")
    wheel_carrier = pinned("release-wheel-carrier-image")
    skip = os.environ.get("RELEASE_VERIFY_SKIP", "")
    steps = []

    publish_after = ["plan_verify"]
    if skip:
        subprocess.run(
            [
                "buildkite-agent", "annotate", "--style", "warning",
                "--context", "release-verify",
                f"TPU check skipped (RELEASE_VERIFY_SKIP): {skip}"
            ],
            check=True,
        )
    else:
        steps.append({
            "label":
            ":test_tube: Verify the image and the wheels on TPU",
            "key":
            "verify_on_tpu",
            "depends_on": ["plan_verify"],
            "trigger":
            os.environ.get("RELEASE_VERIFY_PIPELINE",
                           "tpu-inference-release-verify"),
            # Wait for the triggered build and fail with it, so plan_publish
            # (and the approval block) only comes after it passes.
            "async":
            False,
            "build": {
                "commit":
                os.environ["BUILDKITE_COMMIT"],
                "branch":
                os.environ["BUILDKITE_BRANCH"],
                "message":
                (f"Verify tpu-inference {version} on TPU "
                 f"(release build {os.environ['BUILDKITE_BUILD_URL']})"),
                "env": {
                    "RELEASE_IMAGE_REF": staged,
                    "WHEEL_CARRIER_IMAGE_REF": wheel_carrier,
                },
            },
        })
        publish_after = ["verify_on_tpu"]

    steps.append({
        "label": ":pipeline: Plan the approval and publish",
        "key": "plan_publish",
        "depends_on": publish_after,
        "agents": QUEUE,
        "commands": [PLAN_PUBLISH_CMD],
    })
    print(json.dumps({"steps": steps}, indent=2))


if __name__ == "__main__":
    main()
