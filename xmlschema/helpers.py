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
This module contains various helper functions and classes.
"""
import re
from decimal import Decimal

from .compat import string_base_type
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .qnames import XSD_ANNOTATION

XSD_FINAL_ATTRIBUTE_VALUES = {'restriction', 'extension', 'list', 'union'}
NAMESPACE_PATTERN = re.compile(r'{([^}]*)}')


def get_namespace(name):
    try:
        return NAMESPACE_PATTERN.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


def get_qname(uri, name):
    """
    Returns an expanded QName from URI and local part. If any argument has boolean value
    `False` or if the name is already an expanded QName, returns the *name* argument.

    :param uri: namespace URI
    :param name: local or qualified name
    :return: string or the name argument
    """
    if not uri or not name or name[0] in ('{', '.', '/', '['):
        return name
    else:
        return '{%s}%s' % (uri, name)


def local_name(qname):
    """
    Return the local part of an expanded QName or a prefixed name. If the name
    is `None` or empty returns the *name* argument.

    :param qname: an expanded QName or a prefixed name or a local name.
    """
    try:
        if qname[0] == '{':
            _, qname = qname.split('}')
        elif ':' in qname:
            _, qname = qname.split(':')
    except IndexError:
        return ''
    except ValueError:
        raise XMLSchemaValueError("the argument 'qname' has a wrong format: %r" % qname)
    except TypeError:
        if qname is None:
            return qname
        raise XMLSchemaTypeError("the argument 'qname' must be a string-like object or None")
    else:
        return qname


def qname_to_prefixed(qname, namespaces):
    """
    Transforms a fully qualified name into a prefixed name using a namespace map.
    Returns the *qname* argument if it's not a fully qualified name or if it has
    boolean value `False`.

    :param qname: an extended QName or a local name.
    :param namespaces: a map from prefixes to namespace URIs.
    :return: a QName in prefixed format or a local name.
    """
    if not qname:
        return qname

    namespace = get_namespace(qname)
    for prefix, uri in sorted(filter(lambda x: x[1] == namespace, namespaces.items()), reverse=True):
        if not uri:
            return '%s:%s' % (prefix, qname) if prefix else qname
        elif prefix:
            return qname.replace('{%s}' % uri, '%s:' % prefix)
        else:
            return qname.replace('{%s}' % uri, '')
    else:
        return qname


def qname_to_extended(qname, namespaces):
    """
    Converts a QName in prefixed format or a local name to the extended QName format.

    :param qname: a QName in prefixed format or a local name.
    :param namespaces: a map from prefixes to namespace URIs.
    :return: a QName in extended format or a local name.
    """
    try:
        if qname[0] == '{' or not namespaces:
            return qname
    except IndexError:
        return qname

    try:
        prefix, name = qname.split(':', 1)
    except ValueError:
        if not namespaces.get(''):
            return qname
        else:
            return '{%s}%s' % (namespaces[''], qname)
    else:
        try:
            uri = namespaces[prefix]
        except KeyError:
            return qname
        else:
            return u'{%s}%s' % (uri, name) if uri else name


def get_xsd_annotation(elem):
    """
    Returns the annotation of an XSD component.

    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation, `None` if \
    the XSD information item doesn't have an annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION else None
    except (TypeError, IndexError):
        return


def get_xsd_derivation_attribute(elem, attribute, values=None):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param values: sequence of admitted values when the attribute value is not '#all'.
    :return: a string.
    """
    value = elem.get(attribute)
    if value is None:
        return ''

    if values is None:
        values = XSD_FINAL_ATTRIBUTE_VALUES

    items = value.split()
    if len(items) == 1 and items[0] == '#all':
        return ' '.join(values)
    elif not all(s in values for s in items):
        raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute))
    return value


def get_xsd_form_attribute(elem, attribute):
    """
    Get an XSD form attribute, checking the value. If the attribute is missing returns `None`

    :param elem: the Element instance.
    :param attribute: the attribute name (maybe 'form', or 'elementFormDefault' or 'attributeFormDefault').
    :return: a string.
    """
    value = elem.get(attribute)
    if value is None:
        return
    elif value not in ('qualified', 'unqualified'):
        raise XMLSchemaValueError(
            "wrong value %r for attribute %r, it must be 'qualified' or 'unqualified'." % (value, attribute)
        )
    return value


def count_digits(number):
    """
    Counts the digits of a number.

    :param number: an int or a float or a Decimal or a string representing a number.
    :return: a couple with the number of digits of the integer part and \
    the number of digits of the decimal part.
    """
    if isinstance(number, string_base_type):
        number = str(Decimal(number)).lstrip('-+')
    else:
        number = str(number).lstrip('-+')

    if 'E' in number:
        significand, _, exponent = number.partition('E')
    elif 'e' in number:
        significand, _, exponent = number.partition('e')
    elif '.' not in number:
        return len(number.lstrip('0')), 0
    else:
        integer_part, _, decimal_part = number.partition('.')
        return len(integer_part.lstrip('0')), len(decimal_part.rstrip('0'))

    significand = significand.strip('0')
    exponent = int(exponent)

    num_digits = len(significand) - 1 if '.' in significand else len(significand)
    if exponent > 0:
        return num_digits + exponent, 0
    else:
        return 0, num_digits - exponent - 1


class ParticleCounter(object):
    """
    An helper class for counting total min/max occurrences of XSD particles.
    """
    def __init__(self):
        self.min_occurs = self.max_occurs = 0

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.min_occurs, self.max_occurs)

    def __add__(self, other):
        self.min_occurs += other.min_occurs
        if self.max_occurs is not None:
            if other.max_occurs is None:
                self.max_occurs = None
            else:
                self.max_occurs += other.max_occurs
        return self

    def __mul__(self, other):
        self.min_occurs *= other.min_occurs
        if self.max_occurs is None:
            if other.max_occurs == 0:
                self.max_occurs = 0
        elif other.max_occurs is None:
            if self.max_occurs != 0:
                self.max_occurs = None
        else:
            self.max_occurs *= other.max_occurs
        return self

    def reset(self):
        self.min_occurs = self.max_occurs = 0
