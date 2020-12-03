#! /usr/bin/env python3

#
# lokilogs - send weka cluster events to a Loki server
#
# Author: Vince Fleming, vince@weka.io
#

# example of usage grafana/loki api when you need push any log/message from your python scipt
import argparse
import os
import subprocess
import requests
import json
import datetime
import dateutil
import dateutil.parser
#import syslog
import sys
import signal
import traceback
import time
import urllib3
import wekacluster
from wekaapi import WekaApi
from wekatime import wekatime_to_lokitime, lokitime_to_wekatime, wekatime_to_datetime, lokitime_to_datetime, datetime_to_wekatime, datetime_to_lokitime
from logging import debug, info, warning, error, critical, getLogger, DEBUG, StreamHandler, Formatter

log = getLogger(__name__)

# convert weka/Loki timestamps
def wekatime_to_lokitime(wekatime):
    #log.debug(f"wekatime={wekatime}")
    eventtime = wekatime_to_datetime(wekatime)
    return( datetime_to_lokitime(eventtime) )

def lokitime_to_wekatime(lokitime):
    dt = lokitime_to_datetime(lokitime)
    wekatime = dt.isoformat() + "Z"
    #log.debug(f"wekatime={wekatime}")
    return( wekatime )

def wekatime_to_datetime(wekatime):
    return( dateutil.parser.parse( wekatime ) )

def lokitime_to_datetime(lokitime):
    return( datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=int(lokitime)/1000000000) )

def datetime_to_wekatime(dt):
    wekatime = dt.isoformat() + "Z"
    #log.debug(f"wekatime={wekatime}")
    return( wekatime )

def datetime_to_lokitime(dt):
    return( str(int(dt.timestamp() * 1000000000)) )

class LokiServer(object):
    def __init__(self, lokihost, lokiport):
        self.host = lokihost
        self.port = lokiport

    # push msg log into grafana-loki
    def loki_logevent( self, timestamp, event, **labels ):
        url = 'http://' + self.host + ':' + str(self.port) + '/loki/api/v1/push'   # set the URL

        # set the headers
        headers = {
            'Content-type': 'application/json'
        }

        log.debug(f"{labels}")
        # set the payload
        payload = {
            'streams': [
                {
                    'stream': labels["labels"],
                    'values':[
                        [ timestamp, event ]
                    ]
                }
            ]
        }

        # encode payload to a string
        payload_str = json.dumps(payload)
        #log.debug( json.dumps(payload, indent=4, sort_keys=True) )

        # this is where we actually send it
        try:
            answer = requests.post(url, data=payload_str, headers=headers)
        except Exception as exc:
            log.critical(f"{exc} caught")
            return( False )

        # check the return code
        if answer.status_code == 400:
            # I've only seen code 400 for duplicate entries; but I could be wrong. ;)
            log.error(f"Error posting event; possible duplicate entry: {answer.text}")
            return( True )  # ignore the error so we don't retry submission forever
        elif answer.status_code != 204:  # 204 is ok
            log.error( "loki_logevent(): bad http status code: " + str( answer.status_code ) + " " + answer.text )
            return( False )

        return( True )

        # end loki_logevent

    # format the events and send them up to Loki
    def send_events(self, event_dict, cluster):

        num_successful = 0

        if len(event_dict) == 0:
            log.debug("No events to send")
            return

        # must be sorted by timestamp or Loki will reject them
        last_eventtime = "0"
        for timestamp, event in sorted(event_dict.items()): # oldest first
            labels = {
                "type": "weka",
                "cluster": cluster.name
            }
                #"category": event["category"],
                #"type": event["type"],
                #"severity": event["severity"],
                #"node_id": event["nid"],

            # map weka event severities to Loki event severities
            if event['severity'] == 'MAJOR' or event['severity'] == 'MINOR':
                event['severity'] = 'ERROR'
            elif event['severity'] == 'CRITICAL':
                event['severity'] = 'FATAL'

            description = f"cluster:{cluster.name} :{event['severity']}: {event['type']}: {event['description']}"
            log.debug(f"sending event: timestamp={timestamp}, labels={labels}, desc={description}")

            if self.loki_logevent( timestamp, description, labels=labels ):
                # only update time if upload successful, so we don't drop events (they should retry upload next time)
                #cluster.last_event_timestamp = datetime_to_wekatime( datetime.datetime.utcnow() )
                #cluster.last_event_timestamp = lokitime_to_wekatime( timestamp ) # take the event timestamp?
                num_successful += 1

        log.info(f"Total events={len(event_dict)}; successfully sent {num_successful} events")
        if num_successful != 0:
            cluster.last_event_timestamp = cluster.last_get_events_time

        # end send_events

    # example:
    #https://api.home.weka.io/api/23a0d764-e77d-48d3-ab28-4cdd7167a822/events/list?intr=f&dt=f&svr=INFO&frm=2019-11-24T16:20:06.0352292Z&srt=dsc&lmt=50&to=2020-11-23T16:20:06.0353582Z

    # moved to wekacluster.py
    # get events from Weka
    #def get_events( self, cluster ):
    #    log.debug( "getting events" )

    #    end_time = datetime_to_wekatime(datetime.datetime.utcnow())
    #    events = cluster.home_events( 
    #                num_results=100,
    #                start_time=cluster.last_event_timestamp, 
    #                end_time,
    #                severity="INFO" )

    #    # note the time of this last fetch, if it was successful (failure will cause exception)
    #    self.last_get_events_time = end_time

    #    return reformat_events( events )

        # ------------- end get_events() ----------

#"""
# Adds a description to the events
#def format_descriptions( events, event_descs ):
#
#    for event in events:
#        event_type = event["type"]
#        if event_type in event_descs:
#            format_string = event_descs[event_type]["formatString"]
#            params = event["params"]
#            event["description"] = format_string.format(**params)
#        else:
#            log.debug(f"unknown event type {event['type']}")
#
#    # end of format_descriptions
#"""

# Not used anymore... but might come in handy
# get the time of the last event that Loki has for this cluster so we know where we left off
def last_lokievent_time(lokihost, port, cluster):
    http_pool = urllib3.PoolManager()
    log.debug( "getting last event from Loki" )
    #url = 'http://' + lokihost + ':' + str(port) + '/loki/api/v1/query'   # set the URL
    url = 'http://' + lokihost + ':' + str(port) + '/loki/api/v1/query_range'   # set the URL

    # set the headers
    headers = {
        'Content-type': 'application/json'
    }

    clusternamequery = "{cluster=\"" + f"{cluster.name}" + "\"}"
    fields={
            #'direction': "BACKWARDS",
            'query': clusternamequery
            }
    try:
        latest = http_pool.request( 'GET', url, fields=fields )
    except Exception as exc:
        log.debug(f"{exc} caught")
        return( "0" )

    if latest.status != 200:
        return( "0" )

    log.debug(f"{latest.status} {latest.data}")
    latest_data = json.loads( latest.data )

    newest = 0
    #log.debug(f"latest_data={json.dumps(latest_data, indent=4)}")
    results = latest_data["data"]["result"]
    for result in results:
        values = result["values"]
        for value in values:
            if int(value[0]) > newest:
                newest = int(value[0])
            log.debug(f"timeval={lokitime_to_wekatime(value[0])}")

    first_result = str(newest)

    log.debug(f"first_result={first_result}, {lokitime_to_wekatime(first_result)}")

    return( first_result )

    # end last_lokievent_time

# in case we want it in Wekatime format (ISO8601)
#def last_wekaevent_time(lokihost, port, cluster):
#    return( lokitime_to_wekatime(last_lokievent_time(lokihost, port, cluster)) )


# moved to wekacluster.py
## takes in a list of dicts - [{event},{event},{event}].  Change to a dict of {timestamp:{event},timestamp:{event}} so we can sort by timestamp
#def reformat_events( weka_events ):
#    event_dict={}
#    for event in weka_events:
#        event_dict[wekatime_to_lokitime(event["timestamp"])] = event
#    return event_dict

        # debugging
        #origtime = event["timestamp"]
        #wekatime = lokitime_to_wekatime( lokitime )
        #event_dict[ lokitime ] = event
        #log.debug(f"{origtime} = {lokitime} = {wekatime}")

if __name__ == '__main__':

    # Globals
    target_host=""
    target_port=0
    loki_host=""
    verbose=0

    parser = argparse.ArgumentParser(description="Loki Log Exporter for Weka clusters")
    parser.add_argument("-c", "--configfile", dest='configfile', default="./weka-metrics-exporter.yml", help="override ./weka-metrics-exporter.yml as config file")
    parser.add_argument("-p", "--port", dest='port', default="3100", help="TCP port number to listen on")
    parser.add_argument("-H", "--HOST", dest='wekahost', default="localhost", help="Specify the Weka host(s) (hostname/ip) to collect stats from. May be a comma-separated list")
    parser.add_argument("-L", "--LOKIHOST", dest='lokihost', default="localhost", help="Specify the hostname of the Loki server" )
    parser.add_argument("-v", "--verbose", dest='verbose', action="count", help="Enable verbose output" )
    args = parser.parse_args()

    target_host=args.wekahost   # make sure we can give a list in case one or more are not reachable
    target_port=args.port
    loki_host=args.lokihost
    verbose=args.verbose

    # initially, make sure we seed the list with all past events
    all_events = gather_weka_events( target_host )
    sortable_events = reformat_events( all_events )
    send_events( loki_host, sortable_events )

    while True:
        if verbose > 0:
            print( "sleeping" )
        time.sleep( 60 )    # check for events once per minute
        if verbose > 0:
            print( "gathering events" )
        all_events = gather_weka_events( target_host, "10m" )   # maybe make this less?  1m?
        sortable_events = reformat_events( all_events )
        if verbose > 0:
            print( "sending events" )
        send_events( loki_host, sortable_events )

