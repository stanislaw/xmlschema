#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests concerning the W3C XML Schema 1.1 test suite.
Execute this module as script to run the tests. For default all the
schema tests are built and run. To operate a different selection you
can provide the following options:

 --xml: run also XML instance tests
 --xsd10: run only XSD 1.0 tests
 --xsd11: run only XSD 1.1 tests
 --valid: run only tests set as valid
 --invalid: run only tests set as invalid

Additionally you can provide an unlimited list of positive integers to
run only the tests associated with a progressive list of index.
Also the unittest options are accepted (run with --help to show a summary
of available options).
"""
from __future__ import print_function, unicode_literals
import unittest
import argparse
import os.path
import xml.etree.ElementTree as ElementTree
import sys
import warnings

from xmlschema import validate, XMLSchema10, XMLSchema11, XMLSchemaException
from xmlschema.tests import print_test_header

TEST_SUITE_NAMESPACE = "http://www.w3.org/XML/2004/xml-schema-test-suite/"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XSD_VERSION_VALUES = {'1.0 1.1', '1.0', '1.1'}
ADMITTED_VALIDITY = {'valid', 'invalid', 'indeterminate'}

####
# Tests that are incompatible with XSD meta-schema validation or that are postponed
SKIPPED_TESTS = {
    # Signed as valid that have to be checked
    '../msData/additional/addB194.xsd',         # invalid xml:lang='enu'
    '../msData/particles/particlesZ001.xsd',    # Invalid in XSD 1.0
    '../msData/simpleType/stE110.xsd',          # Circular xs:union declaration
    '../saxonData/Missing/missing001.xsd',      # missing type (this may be valid in 'lax' mode?)
    '../saxonData/Missing/missing002.xsd',      # missing substitution group
    '../saxonData/Missing/missing003.xsd',      # missing type and substitution group
    '../saxonData/Missing/missing006.xsd',      # missing list item type
    '../saxonData/VC/vc001.xsd',                # VC namespace required
    '../saxonData/VC/vc002.xsd',                # VC namespace required
    '../saxonData/VC/vc014.xsd',                # VC namespace required
    '../saxonData/VC/vc024.xsd',                # VC 1.1? required
    '../saxonData/XmlVersions/xv004.xsd',       # non-BMP chars allowed in names in XML 1.1+

    # Signed as valid that depends by implementation choice
    '../saxonData/Assert/assert-simple007.xsd',     # XPath [err:FOCA0002] invalid lexical value

    # Signed as valid but not implemented yet
    '../saxonData/Assert/assert011.xsd',          # TODO: XPath 2 doc() function in elementpath

    # Invalid that may be valid
    '../msData/additional/adhocAddC002.xsd',      # 4642: Lack of the processor on XML namespace knowledge
    '../msData/additional/test65026.xsd',         # 4712: Lack of the processor on XML namespace knowledge
    '../msData/annotations/annotF001.xsd',        # 4989: Annotation contains xml:lang="" ?? (but xml.xsd allows '')
    '../msData/datatypes/Facets/base64Binary/base64Binary_enumeration003.xsd',  # 7277: check base64 invalid values
    '../msData/datatypes/Facets/anyURI/anyURI_a001.xsd',  # 7292: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_a003.xsd',  # 7294: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_b004.xsd',  # 7310: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_b006.xsd',  # 7312: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/element/elemZ026.xsd',  # 8541: This is good because the head element is abstract
    '../msData/element/elemZ031.xsd',  # 8557: Valid in Python that has arbitrary large integers
    '../msData/group/groupH021.xsd',   # 8679: TODO: wrong in XSD 1.0, good in XSD 1.1
    '../msData/identityConstraint/idC019.xsd',  # 8936: TODO: is it an error?
    '../msData/identityConstraint/idI148.xsd',  # 9291: FIXME attribute::* in a selector (restrict XPath parser)
    '../msData/modelGroups/mgE006.xsd',         # 9712: Is valid (is mg007.xsd invalid for the same reason)

    # Invalid that maybe valid because depends by implementation choices
    '../msData/schema/schG6_a.xsd',     # Schema is valid because the ns import is done once, validation fails.
    '../msData/schema/schG11_a.xsd',    # Schema is valid because the ns import is done once, validation fails.

    # Indeterminate that depends by implementation choices
    '../msData/particles/particlesZ026a.xsd',
    '../msData/schema/schG14a.xsd',
    '../msData/schema/schU3_a.xsd',     # Circular redefines
    '../msData/schema/schU4_a.xsd',     # Circular redefines
    '../msData/schema/schU5_a.xsd',     # Circular redefines
    '../msData/schema/schZ012_a.xsd',   # Comparison of file urls to be case sensitive or not
    '../msData/schema/schZ015.xsd',     # schemaLocation=""

}


def extract_additional_arguments():
    """
    Get and expunge additional simple arguments from sys.argv. These arguments
    are not parsed with argparse but are checked and removed from sys.argv in
    order to avoid errors from argument parsing at unittest level.
    """
    try:
        return argparse.Namespace(
            xml='--xml' in sys.argv,
            version='1.0' if '--xsd10' in sys.argv else '1.1' if '--xsd11' in sys.argv else '1.0 1.1',
            expected=('valid',) if '--valid' in sys.argv else ('invalid',) if '--invalid' in sys.argv
            else ('indeterminate',) if '--unknown' in sys.argv else ADMITTED_VALIDITY,
            verbose='-v' in sys.argv or '--verbose' in sys.argv,
            numbers=[int(sys.argv[k]) for k in range(len(sys.argv))
                     if sys.argv[k].isdigit() and sys.argv[k] != '0' and k and sys.argv[k - 1] != '-k']
        )
    finally:
        sys.argv = [
            sys.argv[k] for k in range(len(sys.argv))
            if sys.argv[k] not in {
                '--xml', '--xsd10', '--xsd11', '--valid', '--invalid', '--unknown'
            } and (not sys.argv[k].isdigit() or sys.argv[k] == '0' or not k or sys.argv[k - 1] == '-k')
        ]


args = extract_additional_arguments()


def fetch_xsd_test_suite():
    parent = os.path.dirname
    xmlschema_test_dir = parent(os.path.abspath(__file__))
    xmlschema_base_dir = parent(parent(xmlschema_test_dir))

    suite_file = os.path.join(parent(xmlschema_base_dir), 'xsdtests/suite.xml')
    if os.path.isfile(suite_file):
        return suite_file
    else:
        raise FileNotFoundError("can't find the XSD suite index file suite.xml ...")


def create_w3c_test_group_case(filename, group_elem, group_num, xsd_version='1.0'):
    """
    Creates a test class for a W3C test group.

    :param filename: the filename of the testSet that owns the testGroup.
    :param group_elem: the Element instance of the test group.
    :param group_num: a positive integer to distinguish and order test groups.
    :param xsd_version: if '1.1' uses XSD 1.1 validator class, otherwise uses the XSD 1.0 validator.
    """
    def get_test_conf(elem):
        schema_test = elem.tag.endswith('schemaTest')
        if schema_test:
            tag = '{%s}schemaDocument' % TEST_SUITE_NAMESPACE
        else:
            tag = '{%s}instanceDocument' % TEST_SUITE_NAMESPACE

        try:
            source_path = elem.find(tag).get('{%s}href' % XLINK_NAMESPACE)
        except AttributeError:
            return
        else:
            if not schema_test and source_path.endswith('.testSet'):
                return
            if source_path in SKIPPED_TESTS:
                if args.numbers:
                    print("Skip test number %d ..." % testgroup_num)
                return

        # Normalize and check file path
        source_path = os.path.normpath(os.path.join(os.path.dirname(filename), source_path))
        if not os.path.isfile(source_path):
            print("ERROR: file %r not found!" % source_path)
            return

        test_conf = {}

        for version in xsd_version.split():
            if version not in args.version:
                continue

            for e in elem.findall('{%s}expected' % TEST_SUITE_NAMESPACE):
                if 'version' not in e.attrib:
                    test_conf[version] = e.attrib['validity']
                elif e.attrib['version'] == version or \
                        e.attrib['version'] == 'full-xpath-in-CTA':
                    test_conf[version] = e.attrib['validity']
                    break

            if version not in test_conf:
                msg = "ERROR: Missing expected validity for XSD version %s in %r of test group %r"
                print(msg % (version, elem, name))
                return
            elif test_conf[version] not in ADMITTED_VALIDITY:
                msg = "ERROR: Wrong validity=%r attribute for XSD version %s in %r test group %r"
                print(msg % (test_conf[version], version, elem, name))
                return
            elif test_conf[version] not in args.expected:
                test_conf.pop(version)
            elif test_conf[version] == 'indeterminate':
                if args.verbose:
                    print("WARNING: Skip indeterminate test group %r" % name)
                test_conf.pop(version)

        if test_conf:
            test_conf['source'] = source_path
        return test_conf

    if args.numbers and testgroup_num not in args.numbers:
        return

    # if testgroup_num not in (4759, 8201, 10874, 10881, 10976, 10981, 14377,
    #                          14420, 14425, 14426, 14457, 14656, 14740, 14945, 15009, 15011):
    #    return

    name = group_elem.attrib['name']
    group_tests = []

    # Get schema/instance path
    for k, child in enumerate(group_elem.iterfind('{%s}schemaTest' % TEST_SUITE_NAMESPACE)):
        if k:
            print("ERROR: multiple schemaTest definition in group %r" % name)
            return
        config = get_test_conf(child)
        if not config:
            return
        group_tests.append(config)

    if args.xml:
        for child in group_elem.iterfind('{%s}instanceTest' % TEST_SUITE_NAMESPACE):
            if 'version' in child.attrib and child.attrib['version'] not in args.version:
                continue
            config = get_test_conf(child)
            if config:
                group_tests.append(config)

    if not group_tests:
        if len(args.expected) > 1 and args.xml:
            print("ERROR: Missing both schemaTest and instanceTest in test group %r" % name)
        return

    # print(ElementTree.tostring(testgroup_elem).decode('utf-8'))

    class TestGroupCase(unittest.TestCase):

        @unittest.skipIf(not any(g['source'].endswith('.xsd') for g in group_tests), 'No schema tests')
        def test_xsd_schema(self):
            for item in filter(lambda x: x['source'].endswith('.xsd'), group_tests):
                source = item['source']
                rel_path = os.path.relpath(source)

                for version, expected in sorted(filter(lambda x: x[0] != 'source', item.items())):
                    schema_class = XMLSchema11 if version == '1.1' else XMLSchema10
                    if expected == 'invalid':
                        message = "schema %s should be invalid with XSD %s" % (rel_path, version)
                        with self.assertRaises(XMLSchemaException, msg=message) as _:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                schema_class(source, use_meta=False)
                    else:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                schema = schema_class(source, use_meta=False)
                        except XMLSchemaException as err:
                            schema = None
                            message = "schema %s should be valid with XSD %s, but an error is raised:" \
                                      "\n\n%s" % (rel_path, version, str(err))
                        else:
                            message = None

                        self.assertIsInstance(schema, schema_class, msg=message)

        @unittest.skipIf(not any(g['source'].endswith('.xml') for g in group_tests), 'No instance tests')
        def test_xml_instances(self):
            if group_tests[0]['source'].endswith('.xsd'):
                schema = group_tests[0]['source']
            else:
                schema = None

            for item in filter(lambda x: not x['source'].endswith('.xsd'), group_tests):
                source = item['source']
                rel_path = os.path.relpath(source)

                for version, expected in sorted(filter(lambda x: x[0] != 'source', item.items())):
                    schema_class = XMLSchema11 if version == '1.1' else XMLSchema10
                    if expected == 'invalid':
                        message = "instance %s should be invalid with XSD %s" % (rel_path, version)
                        with self.assertRaises(XMLSchemaException, msg=message) as _:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                validate(source, schema=schema, cls=schema_class)
                    else:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                validate(source, schema=schema, cls=schema_class)
                        except XMLSchemaException as err:
                            error = "instance %s should be valid with XSD %s, but an error " \
                                    "is raised:\n\n%s" % (rel_path, version, str(err))
                        else:
                            error = None
                        self.assertIsNone(error)

    if not any(g['source'].endswith('.xsd') for g in group_tests):
        del TestGroupCase.test_xsd_schema
    if not any(g['source'].endswith('.xml') for g in group_tests):
        del TestGroupCase.test_xml_instances

    TestGroupCase.__name__ = TestGroupCase.__qualname__ = str(
        'TestGroupCase{0:05}_{1}'.format(group_num, name.replace('-', '_'))
    )
    return TestGroupCase


if __name__ == '__main__':
    index_path = fetch_xsd_test_suite()
    index_dir = os.path.dirname(index_path)

    suite_xml = ElementTree.parse(index_path)
    test_classes = {}
    testgroup_num = 0

    print_test_header()

    if args.verbose:
        print("\n>>>>> ADD TEST GROUPS FROM TESTSET FILES <<<<<\n")

    for testset_elem in suite_xml.iter("{%s}testSetRef" % TEST_SUITE_NAMESPACE):
        href_attr = testset_elem.attrib.get("{%s}href" % XLINK_NAMESPACE, '')
        testset_file = os.path.join(index_dir, href_attr)
        testset_groups = 0

        testset = ElementTree.parse(testset_file)
        testset_version = testset.getroot().get('version', '1.0 1.1')
        if testset_version not in XSD_VERSION_VALUES:
            print("Testset file %r has an invalid version=%r, skip ..." % (href_attr, testset_version))
            continue

        for testgroup_elem in testset.iter("{%s}testGroup" % TEST_SUITE_NAMESPACE):
            testgroup_num += 1

            testgroup_version = testgroup_elem.get('version', testset_version)
            if testgroup_version == 'full-xpath-in-CTA':
                # skip full XPath test for the moment ...
                if args.verbose:
                    print("Skip full XPath test %r ..." % testgroup_elem.get('name'))
                continue
            elif testgroup_version not in XSD_VERSION_VALUES:
                _msg = "Test group %r has an invalid version=%r, skip ..."
                print(_msg % (testgroup_elem.get('name'), testgroup_version))
                continue
            elif testgroup_version not in testset_version:
                if args.verbose:
                    _msg = "Warning: Test group %r version=%r is not included in test set version=%r"
                    print(_msg % (testgroup_elem.get('name'), testgroup_version, testset_version))

            cls = create_w3c_test_group_case(
                filename=testset_file,
                group_elem=testgroup_elem,
                group_num=testgroup_num,
                xsd_version=testgroup_version,
            )
            if cls is not None:
                test_classes[cls.__name__] = cls
                testset_groups += 1

        if args.verbose and testset_groups:
            print("Added {} test groups from {}".format(testset_groups, href_attr))

    if args.verbose:
        print("\n>>>>> RUN TEST GROUPS <<<<<\n")

    globals().update(test_classes)
    unittest.main()
