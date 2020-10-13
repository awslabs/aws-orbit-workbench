#  Copyright 2019 Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  #
#  Licensed under the Amazon Software License (the 'License').
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at
#  #
#    http://aws.amazon.com/asl/
#  #
#  or in the 'license' file accompanying this file. This file is distributed
#  on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#  express or implied. See the License for the specific language governing
#  permissions and limitations under the License.
import argparse
class ArgumentParserNoSysExit(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        raise Exception(message)

parser = ArgumentParserNoSysExit(description='start Redshift connection')
parser.add_argument('-cluster', required=True,
                    help='specify cluster name')
parser.add_argument('-start', action='store_true',
                    help='start cluster if not exists')
parser.add_argument('-reuse', action='store_true',
                    help='reuse cluster if exists')
parser.add_argument('-func', nargs='?', default=None,
                    help='specify cluster function name')
line = '-cluster db_test -reuse -start'
args = line.split(' ')
try:
    args = parser.parse_args(args)
    print(args)
except Exception as e:
    print(str(e))

