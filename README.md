Anaconda
========

Complicated Android stuff


To run Anaconda just execute findFunctions.py somewhere in a terminal

File content:
-findFunctions.py
 contains the code which initializes the tracking of tainted data through the code
 
-trackSockets.py
 contains the code which markes functioncalls as sinks because they leak data to a socket
 
-structure.py
 contains the code which builds a structure based on an APK, it uses Androguard for this
