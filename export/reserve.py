
#
# reservation_list - a list with reservable items
#

# author: Vince Fleming, vince@weka.io

from threading import Lock
from time import sleep

SLEEPTIME=0.1
TIMEOUT=5.0

class reservation_list(object):
    def __init__( self ):
        # list is a [] kind of list
        self._lock = Lock() # make it re-entrant (thread-safe)
        self.available = []
        self.reserved = []

    # reserve an item in the list
    def reserve( self ):
        timeout_counter = TIMEOUT
        while timeout_counter > 0:
            with self._lock:
                if len(self.available) + len(self.reserved) == 0:
                    return None     # nothing in the lists - no hosts at all
                if len(self.available) != 0:
                    item = self.available[0]    # always send back the first in the list
                    self.available.remove(item) # move it to the reserved list
                    self.reserved.append(item)
                    return item
            # release the lock and sleep just a little to give others time to release hosts
            sleep(SLEEPTIME)
            timeout_counter -= SLEEPTIME
        return None

    # return a reserved item
    def release( self, item ):
        with self._lock:
            self.reserved.remove(item)
            self.available.append(item)

    # add an item to the list
    def add( self, item ):
        with self._lock:
            if not (item in self.available or item in self.reserved):
                self.available.append(item)

    def remove( self, item ):
        with self._lock:
            # remove it, regardless of which list it's in
            try:
                self.available.remove(item)
            except:
                self.reserved.remove(item)

    def __len__( self ):
        with self._lock:
            return len(self.available) + len(self.reserved)

    def __str__( self ):
        #track = traceback.print_stack()
        #print(track)
        with self._lock:
            return "available=" + str(self.available) + ",reserved=" + str(self.reserved)

    def __contains__(self, hostname):
        with self._lock:
            uberlist = self.available + self.reserved
            for item in uberlist:
                if str(item) == str(hostname):
                    return True


if __name__ == "__main__":
    hostlist = reservation_list()

    print("add 8 things")
    for i in range(8):
        hostlist.add( "name" + str(i) )

    print( str(hostlist) )

    print("reserve 3 things")
    reserved=[]
    for i in range(3):
        reserved.append(hostlist.reserve())
    print( str(hostlist) )


    print("reserve 4 things")
    for i in range(4):
        reserved.append(hostlist.reserve())
    print( str(hostlist) )

    print("release 3 things")
    for i in range(3):
        item = reserved.pop()
        print( "releasing {}".format(item))
        hostlist.release(item)
    print( str(hostlist) )

    print("remove 3 things")
    for i in range(3):
        print( "removing {}".format(reserved[i]))
        hostlist.remove(reserved[i])
    print( str(hostlist) )

    print("reserve 6 things")
    for i in range(6):
        temp = hostlist.reserve()
        if temp != None:
            reserved.append(temp)
        else:
            print( "reserve() timed out" )
        print( reserved )
        print( str(hostlist) )

    if "name7" in hostlist:
        print( "it's in there")
    else:
        print( "it's NOT in there")






