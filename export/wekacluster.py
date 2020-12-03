
from logging import debug, info, warning, error, critical, getLogger, DEBUG, StreamHandler
import logging

from wekaapi import WekaApi
from wekatime import wekatime_to_lokitime, lokitime_to_wekatime, wekatime_to_datetime, lokitime_to_datetime, datetime_to_wekatime, datetime_to_lokitime
from reserve import reservation_list
import traceback
import urllib3
import datetime
from threading import Lock
import json

log = getLogger(__name__)

class WekaHost(object):
    def __init__( self, hostname, tokenfile=None ):
        self.name = hostname
        self.apitoken = tokenfile
        self.api_obj = None
        self._lock = Lock()
        # do we need a backpointer to the cluster?
        log.debug(f"authfile={tokenfile}")

        try:
            if self.apitoken != None:
                self.api_obj = WekaApi(self.name, token_file=self.apitoken, timeout=10)
            else:
                self.api_obj = WekaApi(self.name, timeout=10)
        except Exception as exc:
            log.error(f"{exc}")

        if self.api_obj == None:
            # can't open API session, fail.
            #log.error("WekaHost: unable to open API session")
            raise Exception("Unable to open API session")

    def call_api( self, method=None, parms={} ):
        with self._lock:    # let's force only one command at a time
            log.debug( "calling Weka API on host {}".format(self.name) )
            return self.api_obj.weka_api_command( method, parms )

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

# per-cluster object 
class WekaCluster(object):

    # collects on a per-cluster basis
    # hostname format is "host1,host2,host3,host4" (can be ip addrs, even only one of the cluster hosts)
    # auth file is output from "weka user login" command.
    # autohost is a bool = should we distribute the api call load among all weka servers
    def __init__( self, hostname, authfile=None, autohost=True ):
        # object instance global data
        self.errors = 0
        self.clustersize = 0
        self.loadbalance = True
        self.orig_hostlist = None
        self.name = ""

        self.cloud_url = None
        self.cloud_creds = None
        self.event_descs = None
        self.cloud_proxy = None
        self.cloud_http_pool = None

        self.orig_hostlist = hostname.split(",")  # takes a comma-separated list of hosts
        self.hosts = reservation_list()
        self.authfile = authfile
        self.loadbalance = autohost
        self.last_event_timestamp = None
        self.last_get_events_time = None

        self.refresh_config()

        # get the cluster name via a manual api call    (failure raises and fails creation of obj)
        api_return = self.call_api( method="status", parms={} )
        self.name = api_return['name']
        self.guid = api_return['guid']

        #log.debug( self.hosts )
        #log.debug( "wekaCluster {} created. Cluster has {} members, {} are online".format(self.name, self.clustersize, len(self.hosts)) )
        # ------------- end of __init__() -------------

    def refresh_config(self):
        if len(self.hosts) == 0:
            # create objects for the hosts; recover from total failure
            for hostname in self.orig_hostlist:
                try:
                    hostobj = WekaHost(hostname, self.authfile)
                except:
                    pass
                else:
                    self.hosts.add(hostobj)
        # get the rest of the cluster (bring back any that had previously disappeared, or have been added)
        self.clustersize = 0
        api_return = self.call_api( method="hosts_list", parms={} )
        for host in api_return:
            hostname = host["hostname"]
            if host["mode"] == "backend":
                self.clustersize += 1
                if host["state"] == "ACTIVE" and host["status"] == "UP":
                    if not hostname in self.hosts:
                        try:
                            hostobj = WekaHost(hostname, self.authfile)
                        except:
                            pass
                        else:
                            self.hosts.add(hostobj)

        # weka-home setup
        self.cloud_url = self.call_api( method="cloud_get_url", parms={} )
        log.critical(f"cloud_url='{self.cloud_url}'")
        self.cloud_creds = self.call_api( method="cloud_get_creds", parms={} )
        temp = self.call_api( method="events_describe", parms={"show_internal":False} )

        # make a dict of {event_type: event_desc}
        self.event_descs = {}
        for event in temp:
            self.event_descs[event["type"]] = event

        # need to do something with this
        self.cloud_proxy = self.call_api( method="cloud_get_proxy", parms={} )
        if len(self.cloud_proxy["proxy"]) != 0:
            log.debug(f"Using proxy={self.cloud_proxy['proxy']}")
            self.cloud_http_pool = urllib3.ProxyManager(self.cloud_proxy["proxy"])
        else:
            self.cloud_http_pool = urllib3.PoolManager()


        log.debug( "wekaCluster {} refreshed. Cluster has {} members, {} are online".format(self.name, self.clustersize, len(self.hosts)) )

    def __str__(self):
        return str(self.name)

    def sizeof(self):
        return len(self.hosts)

    # cluster-level call_api() will retry commands on another host in the cluster on failure
    def call_api( self, method=None, parms={} ):
        host = self.hosts.reserve()
        api_return = None
        while host != None:
            log.debug( "calling Weka API on cluster {}, host {}".format(self.name,host) )
            try:
                api_return = host.call_api( method, parms )
            except Exception as exc:
                # something went wrong...  stop talking to this host from here on.  We'll try to re-establish communications later
                last_hostname = host.name
                self.hosts.remove(host)     # remove it from the hostlist iterable
                host = self.hosts.reserve() # try another host; will return None if none left or failure
                self.errors += 1
                log.error( "cluster={}, error {} spawning command {} on host {}. Retrying on {}.".format(
                        self.name, exc, str(method), last_hostname, str(host)) )
                print(traceback.format_exc())
                continue

            self.hosts.release(host)    # release it so it can be used for more queries
            return api_return

        # ran out of hosts to talk to!
        raise Exception("unable to communicate with cluster")

        # ------------- end of call_api() -------------

    # interface to weka-home
    def home_events( self,
            num_results = None,
            start_time = None,
            end_time = None,
            severity = None,
            type_list = None,
            category_list = None,
            sort_order = None,
            by_digested_time = False,
            show_internal = False
            ):
        # Weka Home uses a different API style than the cluster... 
        url = f"{self.cloud_url}/api/{self.guid}/events/list"
        headers={"Authorization": "%s %s" % (self.cloud_creds["token_type"], self.cloud_creds["access_token"])}

        fields={}
        if num_results != None:
            fields["lmt"] = num_results

        if start_time != None:
            fields["frm"] = start_time

        if end_time != None:
            fields["to"] = end_time

        if severity != None:
            fields["svr"] = severity

        if type_list != None:
            log.error("not implemented")

        if category_list != None:
            log.error("not implemented")

        if sort_order != None:
            fields["srt"] = sort_order

        if by_digested_time:
            fields["dt"] = "t"
        else:
            fields["dt"] = "f"

        if show_internal:
            fields["intr"] = "t"
        else:
            fields["intr"] = "f"

        # get from weka-home
        try:
            resp = self.cloud_http_pool.request( 'GET', url, fields=fields, headers=headers)
        except Exception as exc:
            log.critical(f"GET request failure: {exc}")
            return []

        events = json.loads(resp.data.decode('utf-8'))

        if len(events) == 0:
            log.debug("no events!")
            return []

        # format the descriptions; they don't come pre-formatted
        for event in events:
            event_type = event["type"]
            if event_type in self.event_descs:
                format_string = self.event_descs[event_type]["formatString"]
                params = event["params"]
                event["description"] = format_string.format(**params)
            else:
                log.debug(f"unknown event type {event['type']}")

        #log.debug( json.dumps( events, indent=4, sort_keys=True ) )
        return( events )

    # get events from Weka
    def get_events( self ):
        log.debug( "getting events" )

        end_time = datetime_to_wekatime(datetime.datetime.utcnow())
        events = self.home_events( 
                    num_results=100,
                    start_time=self.last_event_timestamp, 
                    end_time=end_time,
                    severity="INFO" )

        # note the time of this last fetch, if it was successful (failure will cause exception)
        self.last_get_events_time = end_time

        return self.reformat_events( events )

        # ------------- end get_events() ----------

    # takes in a list of dicts - [{event},{event},{event}].  Change to a dict of {timestamp:{event},timestamp:{event}} so we can sort by timestamp
    def reformat_events( self, weka_events ):
        event_dict={}
        for event in weka_events:
            event_dict[wekatime_to_lokitime(event["timestamp"])] = event
        return event_dict


if __name__ == "__main__":
    logger = getLogger()
    logger.setLevel(DEBUG)
    log.setLevel(DEBUG)
    FORMAT = "%(filename)s:%(lineno)s:%(funcName)s():%(message)s"
    # create handler to log to stderr
    console_handler = StreamHandler()
    console_handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(console_handler)

    print( "creating cluster" )
    cluster = WekaCluster( "172.20.0.128,172.20.0.129,172.20.0.135" )

    print( "cluster created" )

    print(cluster)

    print( cluster.call_api( method="status", parms={} ) )



















