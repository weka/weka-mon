
#
# wekaapi module
#
# Python implementation of the Weka JSON RPC API.
#
# Author: Vince Fleming, vince@weka.io
#

from __future__ import division, absolute_import, print_function, unicode_literals
try:
    from future_builtins import *
except ImportError:
    pass

import sys
import os
import json
import time
import uuid
import socket
import ssl
import traceback
from threading import Lock

try:
    import http.client
    httpclient = http.client
except ImportError:
    import httplib
    httpclient = httplib

try:
    from urllib.parse import urlencode, urljoin, urlparse
except ImportError:
    from urlparse import urljoin, urlparse

from logging import debug, info, warning, error, critical, getLogger, DEBUG, StreamHandler, Formatter

log = getLogger(__name__)
 
class HttpException(Exception):
    def __init__(self, error_code, error_msg):
        self.error_code = error_code
        self.error_msg = error_msg

#class JsonRpcException(Exception):
#    def __init__(self, json_error):
#        self.orig_json = json_error
#        self.code = json_error['code']
#        self.message = json_error['message']
#        self.data = json_error.get('data', None)


class WekaApiException(Exception):
    def __init__(self, message):
        self.message = message

class WekaApi():
    def __init__(self, host, scheme='https', port=14000, path='/api/v1', timeout=10, tokens=None ):

        self._lock = Lock() # make it re-entrant (thread-safe)
        self._scheme = scheme
        self._host = host
        self._port = port
        self._path = path
        self._conn = None
        self._timeout = timeout
        self.headers = {}
        self._tokens=tokens
        
        log.debug( f"tokens are {self._tokens}" )
        if self._tokens != None:
            self.authorization = '{0} {1}'.format(self._tokens['token_type'], self._tokens['access_token'])
            self.headers["Authorization"] = self.authorization
        else:
            self.authorization = None

        self.headers['UTC-Offset-Seconds'] = time.altzone if time.localtime().tm_isdst else time.timezone
        self.headers['CLI'] = False
        self.headers['Client-Type'] = 'WEKA'

        self._open_connection()
        log.debug(f"WekaApi: connected to {self._host}")

    @staticmethod
    def format_request(message_id, method, params):
        return dict(jsonrpc='2.0',
                    method=method,
                    params=params,
                    id=message_id)

    @staticmethod
    def unique_id(alphabet='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        number = uuid.uuid4().int
        result = ''
        while number != 0:
            number, i = divmod(number, len(alphabet))
            result = alphabet[i] + result
        return result


    @staticmethod
    def _parse_url(url, default_port=14000, default_path='/api/v1'):
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme if parsed_url.scheme else "https"
        if scheme not in ['http', 'https']:
            scheme = "https"
        m = re.match('^(?:(?:http|https)://)?(.+?)(?::(\d+))?(/.*)?$', str(url), re.I)
        assert m
        return scheme, m.group(1), m.group(2) or default_port, m.group(3) or default_path

    def _open_connection( self ):
        host_unreachable=False
        try_again = True

        if self._conn == None:  # only if we don't have a connection already
            while try_again:
                log.debug(f"attempting to open connection: timeout={self._timeout}, scheme={self._scheme}, host={self._host}, port={self._port}")
                try:
                    if self._scheme == "https":
                        self._conn = httpclient.HTTPSConnection(self._host, self._port, timeout=self._timeout)
                        #log.debug( f"HTTPSConnection succeeded {self.host}" )
                    else:
                        self._conn = httpclient.HTTPConnection(self._host, self._port, timeout=self._timeout)
                except Exception as exc:
                    log.critical( f"HTTPConnection {exc}: unable to open connection to {self.host}" )
                    host_unreachable = True

                if not host_unreachable:
                    try:
                        # test a command?
                        self._login()   # should we be doing this here?
                        return
                    except ssl.SSLError:
                        # https failed, try http - http would never produce an ssl error
                        log.debug( "https failed, trying http" )
                        self._scheme = "http"
                        try_again = True
                    except socket.timeout:
                        if self._scheme == "https":
                            # https failed, try http - http would never produce an ssl error
                            log.debug( "https timed out, trying http" )
                            self._scheme = "http"
                            try_again = True
                        else:
                            log.debug("http timed out")
                            host_unreachable=True
                            try_again = False
                    except socket.gaierror: # general failure
                        log.debug("socket.gaierror")
                        host_unreachable=True
                        try_again = False
                    except ConnectionRefusedError as exc:
                        log.debug("connection refused")
                        host_unreachable=True
                        try_again = False
                    except Exception as exc:   # any other failure
                        track = traceback.format_exc()
                        log.debug(track)
                        log.critical(f"Login Failure:{exc}")
                        host_unreachable=True
                        try_again = False

            if host_unreachable:
                raise WekaApiException( "unable to open connection to host " + self._host )

    # end of _open_connection()


    # reformat data returned so it's like the weka command's -J output
    @staticmethod
    def _format_response( method, response_obj ):
        raw_resp = response_obj["result"] 
        if method == "status":
            return( raw_resp )

        resp_list = []

        if method == "stats_show":
            for key, value_dict in raw_resp.items():
                stat_dict = {}
                stat_dict["node"] = key
                stat_dict["category"] = list(value_dict.keys())[0]
                cat_dict = value_dict[stat_dict["category"]][0]
                stats = cat_dict["stats"]
                stat_dict["stat_type"] = list(stats.keys())[0]
                tmp = stats[stat_dict["stat_type"]]
                if tmp == "null":
                    stat_dict["stat_value"] = 0
                else:
                    stat_dict["stat_value"] = tmp
                stat_dict["timestamp"] = cat_dict["timestamp"]
                resp_list.append( stat_dict )
            return resp_list

        splitmethod = method.split("_")
        words = len( splitmethod )

        # does it end in "_list"?
        if method != "alerts_list":
            if splitmethod[words-1] == "list" or method == "filesystems_get_capacity":
                for key, value_dict in raw_resp.items():
                    newkey = key.split( "I" )[0].lower() + "_id"
                    value_dict[newkey] = key
                    resp_list.append( value_dict )
                # older weka versions lack a "mode" key in the hosts-list
                if method == "hosts_list":
                    for value_dict in resp_list:
                        if "mode" not in value_dict:
                            if "drives_dedicated_cores" != 0:
                                value_dict["mode"] = "backend"
                            else:
                                value_dict["mode"] = "client"
                return resp_list

        # ignore other method types for now.
        return raw_resp
    # end of _format_response()

    # log into the api  # assumes that you got an UNAUTHORIZED (401)
    def _login( self ):
        login_message_id = self.unique_id()

        if self.authorization != None:   # maybe should see if _tokens != None also?
            # try to refresh the auth since we have prior authorization
            params = dict(refresh_token=self._tokens["refresh_token"])
            login_request = self.format_request(login_message_id, "user_refresh_token", params)
            log.debug(f"reauthorizing with host {self._host}")
        else:
            # try default login info - we have no tokens.
            params = dict(username="admin", password="admin")
            login_request = self.format_request(login_message_id, "user_login", params)
            log.debug(f"default login with host {self._host} {login_request}" )


        self._conn.request('POST', self._path, json.dumps(login_request), self.headers) # POST a user_login request
        response = self._conn.getresponse()
        response_body = response.read().decode('utf-8')

        if response.status != 200:  # default login creds/refresh failed
            log.critical(f"Login failed on host {self._host}: status {response.status}")
            raise HttpException(response.status, response_body)

        response_object = json.loads(response_body)
        self._tokens = response_object["result"]
        if self._tokens != {}:
            self.authorization = '{0} {1}'.format(self._tokens['token_type'], self._tokens['access_token'])
        else:
            self.authorization = None
            self._tokens= None
            log.critical(f"Login failed on host {self._host}")
            raise WekaApiException(f"Login failed on host {self._host}" )

        self.headers["Authorization"] = self.authorization
        log.debug(f"login to {self._host} successful")

        # end of _login()

    def weka_api_command(self, method, parms):
        lock_timer = time.time()
        # need to make locking more granular
        with self._lock:        # make it thread-safe - just in case someone tries to do 2 commands at the same time
            now = time.time()
            if now - lock_timer > .0001:
                log.debug(f"lock time = {now-lock_timer}s")
            message_id = self.unique_id()
            #log.debug(f"method={method}, parms={parms}")

            request = self.format_request(message_id, method, parms)

            log.debug(f"submitting command to {self._host}: {method} {parms}")

            #logginglevel = log.getEffectiveLevel()

            for i in range(3):  # give it 3 tries
                request_exception = None

                log.debug(f"Making POST request to {self._host}:")
                # lock this?
                self._open_connection() # will only open a connection if there is none

                try:
                    # POST takes no time... wait below
                    self._conn.request('POST', self._path, json.dumps(request), self.headers)
                    log.debug(f"POST successful to {self._host}")
                except http.client.CannotSendRequest as exc:
                    log.debug(f"CannotSendRequest from {self._host}: {self._path} {json.dumps(request)} {str(self.headers)}; aborting")
                    #log.debug( "CannotSendRequest to {}: {} {} {}; aborting".format(self._host, self._path, json.dumps(request), str(self.headers)) )
                    request_exception = exc
                except ConnectionRefusedError as exc: # exception on _conn_request()
                    log.debug(f"Connection Refused from {self._host}: {self._path} {json.dumps(request)} {str(self.headers)}; aborting")
                    #log.debug( "Connection Refused from {}: {} {} {}".format(self._host, self._path, json.dumps(request), str(self.headers)) )
                    request_exception = exc
                except BrokenPipeError:
                    log.debug(f"Broken pipe on {self._host}")
                    self._conn = None
                    continue    # don't take any particular action here - just retry; 3 failures result in the below exception

                if request_exception != None:
                    self._conn = None
                    raise WekaApiException(request_exception)

                # wait for a response
                try:
                    # Note: we're waiting for a response HERE - takes 1+ seconds
                    before = time.time()
                    response = self._conn.getresponse()
                    log.debug(f"response time: {time.time()-before}")
                    #log.debug( "response received: {}".format( response ) )
                except (http.client.RemoteDisconnected, http.client.CannotSendRequest) as exc:
                    # This happens when there's an error and the connection is no good (possibly from another thread)
                    log.debug(f"client disconnected?, retrying {self._host}")
                    #self._conn.connect()    # this should happen at the next request anyway (top of loop)
                    continue
                except Exception as exc:
                    log.error( "Unusual exception caught" )
                    track = traceback.format_exc()
                    print(track)
                    log.error( f"{exc}" )  
                    continue

                log.debug(f"getresponse replied with: {str(response)}")
                response_body = response.read().decode('utf-8')
                log.debug(f"response _body is: {str(response_body)}")

                if response.status == httpclient.UNAUTHORIZED:      # not logged in?
                    log.debug( "need to login" )
                    self._login()
                    continue    # go back to the top of the loop and try again now that we're (hopefully) logged in

                if response.status in (httpclient.OK, httpclient.CREATED, httpclient.ACCEPTED):
                    response_object = json.loads(response_body)
                    if 'error' in response_object:
                        #log.setLevel(DEBUG)  # increase level to debug on error (reset later )
                        log.error(f"bad response from {self._host}")
                        raise WekaApiException(response_object['error'])
                    log.debug( "good response from {self._host}")
                    return self._format_response( method, response_object )
                elif response.status == httpclient.MOVED_PERMANENTLY:
                    oldhost = self._host
                    self._scheme, self._host, self._port, self._path = self._parse_url(response.getheader('Location'))
                    log.debug( "redirection: {oldhost} moved to {self._host}")
                    self._conn = None
                    self._open_connection()
                else:
                    log.error(f"unknown error on {self._host}")
                    self._conn = None
                    raise HttpException(response.status, response.reason)

            log.debug(f"other exception '{exc}' occurred on host {self._host}")
            self._conn = None   # make sure we open a new connection next time
            if i == 2:
                raise WekaApiException(f"Error communicating with {self._host}")
            else:
                raise HttpException(response.status, response_body)

# stand-alone func
def get_tokens(token_file):
    error=False
    log.debug(f"token_file={token_file}")
    tokens=None
    if token_file != None:
        path = os.path.expanduser(token_file)
        if os.path.exists(path):
            try:
                with open( path ) as fp:
                    tokens = json.load( fp )
                return tokens
            except Exception as error:
                log.critical(f"unable to open token file {token_file}")
                error=True
        else:
            error=True
            log.error(f"token file {token_file} not found")

    if error:
        #raise WekaApiException('warning: Could not parse {0}, ignoring file'.format(path), file=sys.stderr)
        return None
    else:
        return tokens

#   end of get_tokens()


# main is for testing
def main():
    logger = getLogger()
    logger.setLevel(DEBUG)
    #log.setLevel(DEBUG)
    FORMAT = "%(filename)s:%(lineno)s:%(funcName)s():%(message)s"
    # create handler to log to stderr
    console_handler = StreamHandler()
    console_handler.setFormatter(Formatter(FORMAT))
    logger.addHandler(console_handler)

    api_connection = WekaApi( '172.20.0.128' )

    #parms={u'category': u'ops', u'stat': u'OPS', u'interval': u'1m', u'per_node': True}
    #print( parms)
    #print( json.dumps( api_connection.weka_api_command( "status" ) , indent=4, sort_keys=True))
    #print( json.dumps( api_connection.weka_api_command( "hosts_list" ) , indent=4, sort_keys=True))
    print( json.dumps( api_connection.weka_api_command( "nodes_list" ) , indent=4, sort_keys=True))
    #print( json.dumps( api_connection.weka_api_command( "filesystems_list" ) , indent=4, sort_keys=True))
    #print( json.dumps( api_connection.weka_api_command( "filesystems_get_capacity" ) , indent=4, sort_keys=True))

    # more examples:
    #print( json.dumps(api_connection.weka_api_command( "stats_show", category='ops', stat='OPS', interval='1m', per_node=True ), indent=4, sort_keys=True) )
    #print( api_connection.weka_api_command( "status", fred="mary" ) )   # should produce error; for checking errorhandling



    # ======================================================================


if __name__ == "__main__":
    sys.exit(main())


