# Adapted from openpyxl 3.1.5 (MIT, Copyright (c) 2010 openpyxl); see third_party/licenses/openpyxl-MIT.txt.


def namespaced(obj, tagname, namespace=None):
    """
    Utility to create a namespaced tag for an object
    """

    namespace = getattr(obj, "namespace", None) or namespace
    if namespace is not None:
        tagname = "{%s}%s" % (namespace, tagname)
    return tagname
