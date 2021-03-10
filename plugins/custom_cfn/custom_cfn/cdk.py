# type: ignore

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

import collections
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, cast

import six
import yaml
from aws_cdk.core import CfnInclude, Construct, Environment, IConstruct, NestedStack, Stack, Tags

# /orbit/env_name/teams missing when we do pre_hook. Can not get team context. Moving to new handler.
# from aws_orbit.plugins.helpers import cdk_handler, cdk_prep_team_handler
from aws_orbit.plugins.helpers import cdk_prep_team_handler

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


TAG_MAP = "tag:yaml.org,2002:map"
UNCONVERTED_SUFFIXES = ["Ref", "Condition"]
FN_PREFIX = "Fn::"

NoDatesSafeLoader = yaml.SafeLoader


class CfnYamlLoader(yaml.Loader):
    yaml_implicit_resolvers = {
        k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
        for k, v in NoDatesSafeLoader.yaml_implicit_resolvers.items()
    }

    pass


def multi_constructor(loader, tag_suffix, node):
    """
    Deal with !Ref style function format
    """

    if tag_suffix not in UNCONVERTED_SUFFIXES:
        tag_suffix = "{}{}".format(FN_PREFIX, tag_suffix)

    constructor = None

    if tag_suffix == "Fn::GetAtt":
        constructor = construct_getatt
    elif isinstance(node, yaml.ScalarNode):
        constructor = loader.construct_scalar
    elif isinstance(node, yaml.SequenceNode):
        constructor = loader.construct_sequence
    elif isinstance(node, yaml.MappingNode):
        constructor = loader.construct_mapping
    else:
        raise Exception("Bad tag: !{}".format(tag_suffix))

    return ODict(((tag_suffix, constructor(node)),))


def construct_getatt(node):
    """
    Reconstruct !GetAtt into a list
    """

    if isinstance(node.value, six.text_type):
        return node.value.split(".", 1)
    elif isinstance(node.value, list):
        return [s.value for s in node.value]
    else:
        raise ValueError("Unexpected node type: {}".format(type(node.value)))


def construct_mapping(self, node, deep=False):
    """
    Use ODict for maps
    """

    mapping = ODict()

    for key_node, value_node in node.value:
        key = self.construct_object(key_node, deep=deep)
        value = self.construct_object(value_node, deep=deep)

        mapping[key] = value

    return mapping


class OdictItems(list):
    """
    Helper class to ensure ordering is preserved
    """

    def __init__(self, items):
        new_items = []

        for item in items:

            class C(type(item)):
                def __lt__(self, *args, **kwargs):
                    return False

            new_items.append(C(item))

        return super(OdictItems, self).__init__(new_items)

    def sort(self):
        pass


class ODict(collections.OrderedDict):
    """
    A wrapper for OrderedDict that doesn't allow sorting of keys
    """

    def __init__(self, pairs=[]):
        if isinstance(pairs, dict):
            # Dicts lose ordering in python<3.6 so disallow them
            raise Exception("ODict does not allow construction from a dict")

        super(ODict, self).__init__(pairs)

        old_items = self.items
        self.items = lambda: OdictItems(old_items())


# Customise our loader
CfnYamlLoader.add_constructor(TAG_MAP, construct_mapping)
CfnYamlLoader.add_multi_constructor("!", multi_constructor)


class Team(Stack):
    def __init__(self, scope: Construct, id: str, context: "Context", parameters: Dict[str, Any]) -> None:
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=context.account_id, region=context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{context.name}")

        _logger.debug("Passing Plugin CDK Stack parameters to the Nested stack Cfn parameters")
        NestedCfnStack(self, id="custom-cfn-stack", parameters=parameters)


class NestedCfnStack(NestedStack):
    def __init__(self, scope: Construct, id: str, parameters: Dict[str, Any]) -> None:
        super().__init__(scope=scope, id=id, parameters=parameters)
        template_path = parameters["CfnTemplatePath"]
        _logger.debug(f"CfnTemplatePath={template_path}")
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"CloudFormation template not found at {template_path}")

        custom_cfn_yaml = yaml.load(open(template_path).read(), Loader=CfnYamlLoader)
        _logger.debug("Yaml loading compelted")
        CfnInclude(self, id="custom-cfn-nested-stack", template=custom_cfn_yaml)
        _logger.debug("Nested stack addition completed")


if __name__ == "__main__":
    cdk_prep_team_handler(stack_class=Team)
