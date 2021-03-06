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

"""Main script for mimic.

This file should be as small as possible and only contain code that is not
going to be tested outside of App Engine.
"""

import cStringIO
from email import feedparser
import sys
import traceback


from __mimic import common
from __mimic import mimic
from __mimic import target_env
from __mimic import target_errors

_SEPARATOR = '-' * 50 + '\n'


class Mimic(object):
  """WSGI app which handles all requests destined for the target app."""

  def __init__(self, environ, start_response):
    self.environ = environ
    self.start_response = start_response

  def __iter__(self):
    saved_in = sys.stdin
    sys.stdin = self.environ['wsgi.input']
    output = cStringIO.StringIO()
    saved_out = sys.stdout
    sys.stdout = output
    try:
      access_key = self.environ.get('mimic.access_key')
      mimic.RunMimic(create_tree_func=common.config.CREATE_TREE_FUNC,
                     access_key=access_key)
    except Exception:
      yield self._ExceptionResponse()
      return
    finally:
      sys.stdin = saved_in
      sys.stdout = saved_out
    response = output.getvalue()
    yield self._NormalResponse(response)

  def _ExceptionResponse(self):
    """Generate an error response."""

    status = '500 Server Error'
    response_headers = [('Content-type', 'text/html; charset=utf-8')]
    self.start_response(status, response_headers)
    return target_errors.ExcInfoAsHtml()

  def _NormalResponse(self, response):
    """Generate a non-error response."""

    # Modelled after appengine/runtime/nacl/python/cgi.py
    parser = feedparser.FeedParser()
    # Set headersonly as we never want to parse the body as an email message.
    parser._set_headersonly()  # pylint: disable-msg=W0212
    parser.feed(response)
    parsed_response = parser.close()
    if 'Status' in parsed_response:
      status = parsed_response['Status']
      del parsed_response['Status']
    else:
      status = '200 OK'
    response_headers = parsed_response.items()
    self.start_response(status, response_headers)
    return parsed_response.get_payload()
