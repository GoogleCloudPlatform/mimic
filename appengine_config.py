import re

from __mimic import datastore_tree
from __mimic import mimic


mimic_CREATE_TREE_FUNC = datastore_tree.DatastoreTree


def namespace_manager_default_namespace_for_request():
  return mimic.GetNamespace()
