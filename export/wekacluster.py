
from logging import debug, info, warning, error, critical, getLogger, DEBUG, StreamHandler
import logging

from wekaapi import WekaApi
import wekaapi
from wekatime import wekatime_to_lokitime, lokitime_to_wekatime, wekatime_to_datetime, lokitime_to_datetime, datetime_to_wekatime, datetime_to_lokitime
from circular import circular_list
import traceback
import urllib3
import datetime
import time
from threading import Lock
import json

log = getLogger(__name__)

class WekaHost(object):
    def __init__(self, hostname, cluster):
        self.name = hostname    # what's my name?
        self.cluster = cluster  # what cluster am I in?
        self.api_obj = None
        self._lock = Lock()
        self.host_in_progress = 0

        #log.debug(f"authfile={tokenfile}")

        try:
            self.api_obj = WekaApi(self.name, tokens=self.cluster.apitoken, timeout=10, scheme=cluster._scheme)
        except Exception as exc:
            log.error(f"Error creating WekaApi object: {exc}")
            #log.error(traceback.format_exc())
            self.api_obj = None

        if self.api_obj == None:
            # can't open API session, fail.
            log.error("WekaHost: unable to open API session")
            raise Exception("Unable to open API session")

        cluster._scheme = self.api_obj.scheme() # scheme is per cluster, if one host is http, all are
        self._scheme = cluster._scheme

    def call_api( self, method=None, parms={} ):
        start_time = time.time()
        self.host_in_progress += 1
        log.debug(f"calling Weka API on host {self}/{method}, {self.host_in_progress} in progress for host")
        try:
            result = self.api_obj.weka_api_command( method, parms )
        except:
            self.host_in_progress -= 1
            raise
        self.host_in_progress -= 1
        log.debug(f"elapsed time for host {self.name}: {time.time() - start_time} secs")
        return result

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        if other == None:
            return False
        elif isinstance(other, WekaHost):
            return other.name == self.name
        elif type(other) == str:
            return other == self.name
        raise NotImplementedError

    def __hash__(self):
        return hash(self.name)

    def scheme(self):
        return self._scheme

# per-cluster object 
class WekaCluster(object):

    # collects on a per-cluster basis
    # clusterspec format is "host1,host2,host3,host4" (can be ip addrs, even only one of the cluster hosts)
    # auth file is output from "weka user login" command.
    # autohost is a bool = should we distribute the api call load among all weka servers
    def __init__(self, clusterspec, authfile=None, autohost=True):
        # object instance global data
        self.errors = 0
        self.clustersize = 0
        self.orig_hostlist = None
        self.name = ""
        self.release = None
        #self._scheme = "https"
        self._scheme = "http"
        self.cluster_in_progress = 0

        self.cloud_url = None
        self.cloud_creds = None
        self.event_descs = None
        self.cloud_proxy = None
        self.cloud_http_pool = None

        self.orig_hostlist = clusterspec.split(",")  # takes a comma-separated list of hosts
        self.hosts = None
        self.host_dict = {}   # host:WekaHost dictionary
        self.authfile = authfile
        self.loadbalance = autohost
        self.last_event_timestamp = None
        self.last_get_events_time = None

        # fetch cluster configuration
        self.apitoken = wekaapi.get_tokens(self.authfile)
        try:
            self.refresh_config()
        except:
            raise

        # get the cluster name via a manual api call    (failure raises and fails creation of obj)
        api_return = self.call_api( method="status", parms={} )
        self.name = api_return['name']
        self.guid = api_return['guid']
        self.release = api_return['release']

        # ------------- end of __init__() -------------

    def __str__(self):
        return str(self.name)

    def sizeof(self):
        return len(self.hosts)

    def refresh_config(self):
        # we need *some* kind of host(s) in order to get the hosts_list below
        if self.hosts == None or len(self.hosts) == 0:
            templist = []
            log.debug(f"Refreshing hostlists from original")
            # create objects for the hosts; recover from total failure
            for hostname in self.orig_hostlist:
                try:
                    hostobj = WekaHost(hostname, self)
                    #self.host_dict[hostname] = hostobj
                    templist.append(hostobj)
                except:
                    pass
            #self.hosts = circular_list(list(self.host_dict.keys()))
            self.hosts = circular_list(templist)

        # get the rest of the cluster (bring back any that had previously disappeared, or have been added)
        try:
            api_return = self.call_api( method="hosts_list", parms={} )
        except:
            raise

        self.clustersize = 0
        templist = []

        for host in api_return:
            hostname = host["hostname"]
            if host["mode"] == "backend":
                self.clustersize += 1
                if host["state"] == "ACTIVE" and host["status"] == "UP":
                    # check if it's already in the list
                    # need a comparison of hostname to hostobj - vince
                    #if hostname not in self.host_dict:
                    if hostname not in self.hosts:
                        try:
                            log.debug(f"creating new WekaHost instance for host {hostname}")
                            hostobj = WekaHost(hostname, self)
                            #self.host_dict[hostname] = hostobj
                            self.hosts.insert(hostobj)
                        except:
                            pass
                    else:
                        log.debug(f"{hostname} already in list")

        #self.hosts = circular_list(templist)
        #self.hosts = circular_list(list(self.host_dict.keys()))

        log.debug(f"host list is: {str(self.hosts)}")

        log.debug( "wekaCluster {} refreshed. Cluster has {} members, {} are online".format(self.name, self.clustersize, len(self.hosts)) )

    # cluster-level call_api() will retry commands on another host in the cluster on failure
    def call_api( self, method=None, parms={} ):
        #hostname = self.hosts.next()
        #if hostname == None:
        #    # no hosts?
        #    raise Exception("unable to communicate with cluster - no hosts in host list")
        #try:
        #    host = self.host_dict[hostname]
        #except:
        #    log.error(f"hostname {hostname} not in host_dict. host_dict={host_dict}")
        #    return
        host = self.hosts.next()

        api_return = None
        while host != None:
            self.cluster_in_progress += 1
            try:
                log.debug(f"calling Weka API on cluster {self}, host {host}, method {method}, {self.cluster_in_progress} in progress for cluster")
                api_return = host.call_api( method, parms )
            except wekaapi.WekaApiIOStopped as exc:
                log.error(f"IO Stopped on Cluster {self}")
                raise
            except Exception as exc:
                self.cluster_in_progress -= 1
                # something went wrong...  stop talking to this host from here on.  We'll try to re-establish communications later
                #last_hostname = hostname
                #self.hosts.remove(last_hostname)     # remove it from the hostlist iterable
                last_hostname = str(host)
                self.hosts.remove(host) # it failed, so remove it from the list
                host = self.hosts.next()
                if host == None:
                    break   # fall through to raise exception
                self.errors += 1
                log.error(f"cluster={self}, {type(exc)} error {exc} spawning command {method} on host {last_hostname}. Retrying on {host}.")
                #print(traceback.format_exc())
                continue

            self.cluster_in_progress -= 1
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

        # weka-home setup
        self.cloud_url = self.call_api( method="cloud_get_url", parms={} )
        log.debug(f"cluster={self.name}, cloud_url='{self.cloud_url}'")
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
            #self.cloud_http_pool = urllib3.PoolManager()
            url = urllib3.util.parse_url(self.cloud_url)
            self.cloud_http_pool = urllib3.HTTPSConnectionPool(url.host, retries=3)

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



















