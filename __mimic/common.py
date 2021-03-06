# Copyright 2012 Google Inc. All Rights Reserved.
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

"""Common classes, functions, and constants for Mimic."""



import json
import logging
import mimetypes
import os
import re

from google.appengine.api import lib_config
from google.appengine.ext import ndb


# The version ID of this mimic. This is used in the auto-update process. This
# number should increase for each version.
VERSION_ID = 1

# URL path prefix for Mimic's control application
CONTROL_PREFIX = '/_ah/mimic'

CONTROL_PATHS_REQUIRING_TREE = [
    CONTROL_PREFIX + '/clear',
    CONTROL_PREFIX + '/delete',
    CONTROL_PREFIX + '/dir',
    CONTROL_PREFIX + '/zip',
    CONTROL_PREFIX + '/file',
    CONTROL_PREFIX + '/move',
]

CONTROL_PATHS_REQUIRING_NAMESPACE = CONTROL_PATHS_REQUIRING_TREE + [
    CONTROL_PREFIX + '/log',
    CONTROL_PREFIX + '/index',
]

RFC_1123_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

# URL path prefix for accessing a Python shell
SHELL_PREFIX = '/_ah/shell'

# TODO: consider https://code.google.com/p/ipaddr-py/
IPV4_REGEX = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')

# match top level '*.appspot.com' hostnames
# - matches 'foo.appspot.com' but not 'bar.foo.appspot.com'
# - assumes '-dot-' has already been normalized to '.'
TOP_LEVEL_APPSPOT_COM_REGEX = re.compile(r'^[^\.]+\.appspot\.com$')

# memcache key space
MEMCACHE_MANIFEST_PREFIX = 'manifest:'
MEMCACHE_FILE_KEY_PREFIX = 'file:'

# persisted names
PERSIST_INDEX_NAME = 'index'

# os.environ key representing 'X-AppEngine-QueueName' HTTP header,
# which should only be present for 'offline' task queue requests, see
# https://developers.google.com/appengine/docs/python/taskqueue/overview-push#Task_Execution
HTTP_X_APPENGINE_QUEUENAME = 'HTTP_X_APPENGINE_QUEUENAME'

# os.environ key representing 'X-AppEngine-Cron' HTTP header,
# which should only be present for 'offline' cron requests, see
# https://developers.google.com/appengine/docs/python/config/cron#Securing_URLs_for_Cron
HTTP_X_APPENGINE_CRON = 'HTTP_X_APPENGINE_CRON'

# os.environ key representing 'X-AppEngine-Current-Namespace' HTTP header,
# which identifies the effective namespace when a task was created
HTTP_X_APPENGINE_CURRENT_NAMESPACE = 'HTTP_X_APPENGINE_CURRENT_NAMESPACE'

_requires_original_memcache_call_depth = 0


config = lib_config.register('mimic', {
    # namespace for mimic specific data
    'NAMESPACE': '_mimic',
    # must be defined in appengine_config.py
    'CREATE_TREE_FUNC': None,
    # regex for extracting project name from PATH_INFO
    'PROJECT_ID_FROM_PATH_INFO_RE': re.compile('/_mimic/p/(.+?)/'),
    # dev_appserver query parameter used to identify the project_id
    'PROJECT_ID_QUERY_PARAM': '_mimic_project',
    # HTTP hosts which may serve user content or None to allow any host
    'ALLOWED_USER_CONTENT_HOSTS': None,
    # allowed CORS origins
    'CORS_ALLOWED_ORIGINS': [],
    # allowed CORS HTTP headers
    'CORS_ALLOWED_HEADERS': 'Origin, Accept',
    # shared JSON encoder, for optional pretty printing
    'JSON_ENCODER': json.JSONEncoder(),
    })

# supplement mimetypes.guess_type()'s limited guessing abilities
_TEXT_MIME_TYPES = {
    'css': 'text/css',

    # *.dart uses *.js MIME Type for now
    'dart': 'text/javascript',

    'go': 'text/x-go',
    'html': 'text/html',
    'ico': 'image/x-icon',

    # .java is reported as x-java-source by mimetypes, which CodeMirror doesn't
    # like, so we override
    'java': 'text/x-java',

    'js': 'text/javascript',
    'jsp': 'application/x-jsp',
    'json': 'application/json',
    'php': 'application/x-httpd-php',
    'sh': 'text/x-sh',
    'sql': 'text/x-mysql',
    'xml': 'application/xml',
    'yaml': 'text/x-yaml',
}


class Error(Exception):
  """Base class for all Mimic exceptions."""


class RequestError(Error):
  """An error caused by a failure to communicate with a remote component."""


# TODO: Unfortunately this model will pollute the target application's
# Datastore. The name (prefixed with _Ah) was chosen to minimize collision,
# but there may be a better mechanism, e.g. by using a namespace.
class _AhMimicPersist(ndb.Model):
  """A model for storing name/value pairs (name is used as a key)."""
  # Some values (eg, the recorded datastore index) require more than 500 bytes,
  # and they also use pickle to encode the data, so TextProperty() can't be
  # used, so BlobProperty is used.
  value = ndb.BlobProperty()


class Tree(object):
  """An abstract base class for accessing a tree of files.

  At minimum subclasses must implement GetFileContents() and HasFile().
  Additionally, mutable trees should override IsMutable() to return True and
  provide implementations of SetFile() and Clear().
  """

  def __init__(self, namespace='', access_key=None):
    """Constructor.

    Args:
      namespace: the datastore/memcache namespace to use
      access_key: key which provides access to this tree
    """
    pass

  @staticmethod
  def _NormalizeDirectoryPath(path):
    """Normalize non empty str to have a trailing '/'."""
    if path and path[-1] != '/':
      return path + '/'
    return path

  def IsMutable(self):
    """Returns True if the tree can be modifed, False otherwise."""
    return False

  def GetFileContents(self, path):
    """Returns the contents of a specified file.

    Args:
      path: The full path for the file.

    Returns:
      A string containing the file's contents, or None if the file does not
      exist.
    """
    raise NotImplementedError

  def GetFileSize(self, path):
    """Returns the size of a specified file.

    Args:
      path: The full path for the file.

    Returns:
      The file's size in bytes, or None if the file does not exist.
    """
    raise NotImplementedError

  def GetFileLastModified(self, path):
    """Returns the time that a file was last updated.

    Args:
      path: The full path for the file.

    Returns:
      The datetime object that represents the time the file was last updated,
      or None if the file does not exist.
    """
    raise NotImplementedError

  def HasFile(self, path):
    """Check if a file exists.

    Args:
      path: The full path for the file.

    Returns:
      True if the file exists, False otherwise.
    """
    raise NotImplementedError

  def MoveFile(self, path, newpath):
    """Move or rename an existing file.

    Args:
      path: The current full path for the file.
      newpath: The new full path for the file.

    Returns:
      True if the file was moved, False otherwise.
    """
    raise NotImplementedError

  def DeletePath(self, path):
    """Delete a file, or directory and its contents.

    Args:
      path: The full path for the file or directory.

    Returns:
      True if any paths were deleted, False otherwise.
    """
    raise NotImplementedError

  def SetFile(self, path, contents):
    """Set the contents for a file.

    Args:
      path: The full path for the file.
      contents: The contents of the file as a string.

    Raises:
      NotImplementedError: If the tree is immutable.
    """
    raise NotImplementedError

  def Clear(self):
    """Removes all files from the tree.

    Raises:
      NotImplementedError: If the tree is immutable.
    """
    raise NotImplementedError

  def HasDirectory(self, path):
    """Check if a directory exists.

    Args:
      path: The full path for the directory.

    Returns:
      True if the directory exists, False otherwise.
      Always returns True for the '/' directory.
    """
    raise NotImplementedError

  def ListDirectory(self, path):
    """Return the contents of a directory.

    Args:
      path: The full path for the directory.

    Returns:
      A list of files and subdirectories.

    Raises:
      OSError: if the requested directory does not exist.
    """
    raise NotImplementedError

  def Files(self, path):
    """Retrieve files in the tree with leading path.

    Args:
      path: The full path for the directory.

    Returns:
      List of (path, contents, last_updated) tuples representing all files in
      the tree.
    """
    raise NotImplementedError

  def PutFiles(self, files):
    """Store files in the tree.

    Args:
      files: List of (path, contents, last_updated) tuples.
    """
    raise NotImplementedError

def IsDevMode():
  """Return True for dev_appserver and tests, False for production."""
  try:
    server_software = os.environ['SERVER_SOFTWARE']
  except KeyError:
    # SERVER_SOFTWARE not set, assume unit tests
    return True
  return server_software.startswith('Development/')


def RequiresOriginalMemcache(func):
  """Disables namespacing memcache with the project's prefix.

  This is a decorator that will prevent the keys used in calls to memcache from
  being prefixed with the project's name for namespacing memcache for the
  duration of the decorated function. This is primarily for allowing mimic to
  cache the target app's files without polluting the target app's namespace.

  Args:
    func: The function which is to be decorated.

  Returns:
    A function object.
  """

  def Wrapper(*args, **kwargs):
    global _requires_original_memcache_call_depth
    _requires_original_memcache_call_depth += 1
    try:
      return func(*args, **kwargs)
    finally:
      _requires_original_memcache_call_depth -= 1
      assert _requires_original_memcache_call_depth >= 0

  return Wrapper


def ShouldUseOriginalMemcache():
  return _requires_original_memcache_call_depth > 0


def GetPersistent(name):
  """Get a persisted value.

  Args:
    name: The name of the value (used to build a key).

  Returns:
    A string value or None if the name cannot be found.
  """
  entity = _AhMimicPersist.get_by_id(name)
  if entity is not None:
    return entity.value

  # no value
  return None


def SetPersistent(name, value):
  """Set a persisted name/value pair.

  Args:
    name: The name of the value (used to build a key).
    value: A string value.
  """
  _AhMimicPersist(id=name, value=value).put()


def ClearPersistent(name):
  """Clear a persisted name."""
  ndb.Key(_AhMimicPersist, name).delete()


def GetExtension(filename):
  """Determine a filename's extension."""
  return filename.lower().split('.')[-1]


def GuessMimeType(filename):
  """Guess the MIME Type based on the provided filename.

  Args:
    filename: the filename for which to determine a suitable MIME Type.

  Returns:
    The MIME Type based on the provided filename's extension.
  """
  extension = GetExtension(filename)
  mime_type = _TEXT_MIME_TYPES.get(extension)
  if not mime_type:
    mime_type, _ = mimetypes.guess_type(filename)
  if not mime_type:
    logging.warning('Failed to guess MIME Type for "%s" with extension "%s"',
                    filename, extension)
  if not mime_type:
    mime_type = 'application/octet-stream'
  if mime_type.startswith('text/') and '; charset=' not in mime_type:
    mime_type += '; charset=utf-8'
  return mime_type
