# -*- coding: utf-8 -*-
from __future__ import print_function

import json

import requests
import requests_cache
import six
from future.builtins import next, object
from future.utils import python_2_unicode_compatible, raise_from
from requests.exceptions import HTTPError, Timeout

from .errors import ApiError, ApiTimeout, AuthenticationError

# Cache GET results for 5min to save Holvis bandwidth (also the API is a bit on the slow side so this makes things faster for us)
requests_cache.install_cache('Nordea-REST', 'memory', expire_after=300)
# Store multiple clientid connections with singleton getter
CONNECTION_MAP = {}


@python_2_unicode_compatible
class Connection(object):
    base_url_fmt = "https://api.nordeaopenbanking.com/v1/"
    session = None
    auth_type = 'authenticated-user-full-access'

    @classmethod
    def singleton(self, clientid, authkey):
        """Get a singleton of a connection"""
        global CONNECTION_MAP
        mapkey = "%s:%s" % (clientid, authkey)
        if not mapkey in CONNECTION_MAP:
            CONNECTION_MAP[mapkey] = Connection(clientid, authkey)
        return CONNECTION_MAP[mapkey]

    def __init__(self, clientid, authkey):
        self.clientid = clientid
        self.key = authkey

    def _init_session(self):
        """Iniitializes a requests.Session for us if not already initialized"""
        if not self.session:
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'x-ibm-client-secret': self.key,
                'x-ibm-client-id': self.clientid,
                'authorization': 'Bearer %s' % self.auth_type
            })
        # 0.4.10 does not yet support this method, add it when new versio comes to pypi
        self.session.remove_expired_responses()

    def make_get(self, url, params={}):
        """Make a GET request"""
        self._init_session()
        r = self.session.get(url, params=params)
        try:
            r.raise_for_status()
        except Timeout as e:
            raise ApiTimeout(e.__str__(), response=e.response)  # six.u messes this up
        except HTTPError as e:
            if e.response.status_code in (403, 401):
                raise AuthenticationError(e.__str__(), response=e.response)  # six.u messes this up
            else:
                raise ApiError(e.__str__(), response=e.response)  # six.u messes this up
        return r.json()

    def make_post(self, url, payload):
        """Make a POST request"""
        return self._make_ppp('post', url, payload)

    def make_put(self, url, payload):
        """Make a PUT request"""
        return self._make_ppp('put', url, payload)

    def make_patch(self, url, payload):
        """Make a PATCH request"""
        return self._make_ppp('patch', url, payload)

    def _make_ppp(self, method, url, payload):
        """Internal helper to make POST/PUT/PATCH requests (or whatever the underlying library supports)"""
        self._init_session()
        # We can't trust the cache after we have made changes of our own
        self.session.cache.clear()
        m = getattr(self.session, method)
        r = m(url, data=json.dumps(payload))
        try:
            r.raise_for_status()
        except Timeout as e:
            raise ApiTimeout(e.__str__(), response=e.response)  # six.u messes this up
        except HTTPError as e:
            if e.response.status_code in (403, 401):
                raise AuthenticationError(e.__str__(), response=e.response)  # six.u messes this up
            else:
                raise ApiError(e.__str__(), response=e.response)  # six.u messes this up
        return r.json()
