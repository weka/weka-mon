
#
# signals module - handle typical signals
#

# author: Vince Fleming, vince@weka.io

import signal
#import syslog
import sys
from logging import debug, getLogger

log = getLogger(__name__)

class signal_handling():
    def __init__( self ):
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGINT, self.sigint_handler)
        signal.signal(signal.SIGHUP, self.sighup_handler)
        log.debug( "signal_handling: signal handlers set" )

    @staticmethod
    def sigterm_handler(signal, frame):
        log.critical('SIGTERM received, exiting')
        sys.exit(0)

    @staticmethod
    def sigint_handler(signal, frame):
        log.critical('SIGINT received, exiting')
        sys.exit(1)

    @staticmethod
    def sighup_handler(signal, frame):
        log.critical('SIGHUP received, exiting')
        sys.exit(0)
