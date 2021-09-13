#!/usr/bin/env bash
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#
#
#   This script should be executed on a newly deployed, clean environment
#   with internet accessbility enabled.

kubectl get pods -A -o yaml | \
    grep "image:" | \
    grep -v "f:image" | \
    sed "s/^.*image: //g" | \
    sort | uniq | \
    grep -vE "k8s-utilities|orbit-controller" \
  > image_inventory.txt
cat extra_images.txt >> image_inventory.txt