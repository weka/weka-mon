
from datetime import datetime, timedelta
from dateutil.parser import parse


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
    #return( dateutil.parser.parse( wekatime ) )
    return( parse( wekatime ) )

def lokitime_to_datetime(lokitime):
    #return( datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=int(lokitime)/1000000000) )
    return( datetime(1970, 1, 1) + timedelta(seconds=int(lokitime)/1000000000) )

def datetime_to_wekatime(dt):
    wekatime = dt.isoformat() + "Z"
    #log.debug(f"wekatime={wekatime}")
    return( wekatime )

def datetime_to_lokitime(dt):
    return( str(int(dt.timestamp() * 1000000000)) )

