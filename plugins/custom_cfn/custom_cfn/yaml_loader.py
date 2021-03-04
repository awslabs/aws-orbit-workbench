# type: ignore

"""
Copyright 2016-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License").
You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions
and limitations under the License.
"""


import collections

import six
import yaml

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
