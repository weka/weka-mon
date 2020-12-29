
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

import urllib3

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

#pool_manager = urllib3.PoolManager(num_pools=100) # new

class WekaApiIOStopped(Exception):
    def __init__(self, message):
        self.message = message

class WekaApiException(Exception):
    def __init__(self, message):
        self.message = message

class WekaApi():
    def __init__(self, host, scheme='http', port=14000, path='/api/v1', timeout=10, tokens=None ):

        self._lock = Lock() # make it re-entrant (thread-safe)
        self._scheme = scheme
        self._host = host
        self._port = port
        self._path = path
        self._conn = None
        self._timeout = timeout
        self.headers = {}
        self._tokens=tokens
        
        # forget scheme (https/http) at this point...   notes:  maxsize means 2 connections per host, block means don't make more than 2
        self.http_conn = urllib3.HTTPConnectionPool(host, port=port, maxsize=2, block=True, retries=3)

        log.debug( f"tokens are {self._tokens}" )
        if self._tokens != None:
            self.authorization = '{0} {1}'.format(self._tokens['token_type'], self._tokens['access_token'])
            self.headers["Authorization"] = self.authorization
        else:
            self.authorization = None

        self.headers['UTC-Offset-Seconds'] = time.altzone if time.localtime().tm_isdst else time.timezone
        self.headers['CLI'] = False
        self.headers['Client-Type'] = 'WEKA'

        self._login()

        log.debug( "WekaApi: connected to {}".format(self._host) )

    def scheme(self):
        return self._scheme

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
        #scheme = parsed_url.scheme if parsed_url.scheme else "https"
        scheme = parsed_url.scheme if parsed_url.scheme else "http"
        if scheme not in ['http', 'https']:
            #scheme = "https"
            scheme = "http"
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
                        log.debug( "https failed" )
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
        log.debug("logging in")

        if self.authorization != None:   # maybe should see if _tokens != None also?
            # try to refresh the auth since we have prior authorization
            params = dict(refresh_token=self._tokens["refresh_token"])
            login_request = self.format_request(login_message_id, "user_refresh_token", params)
            log.debug( "reauthorizing with host {}".format(self._host) )
        else:
            # try default login info - we have no tokens.
            params = dict(username="admin", password="admin")
            login_request = self.format_request(login_message_id, "user_login", params)
            log.debug(f"default login with host {self._host} {login_request}" )


        try:
            api_endpoint = f"{self._scheme}://{self._host}:{self._port}{self._path}"
            log.debug(f"trying {api_endpoint}")
            response = self.http_conn.request('POST', api_endpoint, headers=self.headers, body=json.dumps(login_request).encode('utf-8'))
        except urllib3.exceptions.MaxRetryError as exc:
            # https failed, try http - http would never produce an ssl error
            if isinstance(exc.reason, urllib3.exceptions.SSLError):
                log.debug(f"SSLError detected")
                log.debug( "https failed" )
                self._scheme = "http"
                return self._login() # recurse
            elif isinstance(exc.reason, urllib3.exceptions.NewConnectionError):
                log.critical(f"ConnectionRefusedError/NewConnectionError caught")
                raise WekaApiException( "Login failed" )
            else:
                log.critical(f"MaxRetryError: {exc.reason}")
                track = traceback.format_exc()
                print(track)
                raise
        except Exception as exc:
            log.critical(f"{exc}")
            raise WekaApiException( "Login failed" )

        response_body = response.data.decode('utf-8')

        if response.status != 200:  # default login creds/refresh failed
            raise HttpException(response.status, response_body)

        response_object = json.loads(response_body)

        if "error" in response_object:
            log.critical(f"Error logging into host {self._host}: {response_object['error']['message']}")
            raise WekaApiException( "Login failed" )

        self._tokens = response_object["result"]
        if self._tokens != {}:
            self.authorization = '{0} {1}'.format(self._tokens['token_type'], self._tokens['access_token'])
        else:
            self.authorization = None
            self._tokens= None
            log.critical( "Login failed" )
            raise WekaApiException( "Login failed" )

        self.headers["Authorization"] = self.authorization
        log.debug( "login to {} successful".format(self._host) )

        # end of _login()


    # re-implemented with urllib3
    def weka_api_command(self, method, parms):

        api_endpoint = f"{self._scheme}://{self._host}:{self._port}{self._path}"
        log.debug(f"api_endpoint = {api_endpoint}")
        message_id = self.unique_id()
        request = self.format_request(message_id, method, parms)
        log.debug(f"trying {api_endpoint}")
        try:
            response = self.http_conn.request('POST', api_endpoint, headers=self.headers, body=json.dumps(request).encode('utf-8'))
        except urllib3.exceptions.MaxRetryError as exc:
            # https failed, try http - http would never produce an ssl error
            if isinstance(exc.reason, urllib3.exceptions.SSLError):
                log.debug(f"SSLError detected")
                log.debug("https failed")
                self._scheme = "http"
                return self.weka_api_command(method, parms) # recurse
            elif isinstance(exc.reason, urllib3.exceptions.NewConnectionError):
                log.critical(f"NewConnectionError caught")
            elif isinstance(exc.reason, urllib3.exceptions.ConnectionRefusedError):
                log.critical(f"ConnectionRefusedError caught")
            else:
                log.critical(f"MaxRetryError: {exc.reason}")
            raise
        except Exception as exc:
            log.debug(f"{exc}")
            track = traceback.format_exc()
            print(track)
            return


        #log.info('Response Code: {}'.format(response.status))  # ie: 200, 501, etc
        #log.info('Response Body: {}'.format(resp_body))

        if response.status == httpclient.UNAUTHORIZED:      # not logged in?
            log.debug( "need to login" )
            try:
                self._login()
            except:
                raise
            return self.weka_api_command(method, parms) # recurse - try again


        if response.status in (httpclient.OK, httpclient.CREATED, httpclient.ACCEPTED):
            response_object = json.loads(response.data.decode('utf-8'))
            if 'error' in response_object:
                log.error( "bad response from {}".format(self._host) )
                raise WekaApiIOStopped(response_object['error']['message'])
            log.debug( "good response from {}".format(self._host) )
            return self._format_response( method, response_object )
        elif response.status == httpclient.MOVED_PERMANENTLY:
            oldhost = self._host
            self._scheme, self._host, self._port, self._path = self._parse_url(response.getheader('Location'))
            log.debug( "redirection: {} moved to {}".format(oldhost, self._host) )
        else:
            log.error( "unknown error on {}".format(self._host) )
            raise HttpException(response.status, response.reason)


        resp_dict = json.loads(response.data.decode('utf-8'))
        return self._format_response( method, resp_dict )


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
                log.critical( "unable to open token file {}".format(token_file) )
                error=True
        else:
            error=True
            log.error( "token file {} not found".format(token_file) )

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


