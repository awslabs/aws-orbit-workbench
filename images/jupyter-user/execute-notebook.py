#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple

import papermill as pm

PREFIX = "/efs/shared/scheduled/"


def parse_args() -> Tuple[str, int]:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=str)
    parser.add_argument("timeout", type=int)
    args = parser.parse_args()
    return args.input, args.timeout


def main() -> None:
    time: str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    print(f"time: {time}")
    input, timeout = parse_args()
    print(f"timeout: {timeout}")
    full_input = f"{PREFIX}notebooks/{input}"
    print(f"full_input: {full_input}")
    output_dir = f"{PREFIX}outputs/{input.rsplit('.')[0]}/"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    full_output = f"{output_dir}{time}-running.ipynb"
    print(f"full_output: {full_output}")
    try:
        pm.execute_notebook(
            input_path=full_input,
            output_path=full_output,
            start_timeout=10,
            execution_timeout=timeout,
            progress_bar=False,
        )
    except pm.exceptions.PapermillExecutionError as ex:
        final_output = f"{output_dir}{time}-error-{ex.ename}.ipynb"
        print(f"{ex.ename}: {ex.evalue} at cell {ex.cell_index}.")
    except Exception as ex:
        final_output = f"{output_dir}{time}-error.ipynb"
        print(ex)
    else:
        final_output = f"{output_dir}{time}-sucess.ipynb"
    finally:
        os.rename(full_output, final_output)


if __name__ == "__main__":
    main()
