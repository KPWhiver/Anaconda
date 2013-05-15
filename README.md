Anaconda
========

Anaconda is a static analysis tool which analyzes the data-flow of an APK to determine whether an application is leaking sensitive data.


To run Anaconda just execute anaconda.py somewhere in a terminal, running it without any parameters will result in a help page given more detailed information on how to use Anaconda.

After running Anaconda results will be stored in html/results.html, which can be opened in a browser (we suggest a not to old version of Chrome/Chromium or Firefox)

File content:

-anaconda.py
 contains the code which initializes the tracking of tainted data through the code
 
-trackSockets.py
 contains the code which markes functioncalls as sinks because they leak data to a socket
 
-structure.py
 contains the code which builds a structure based on an APK, it uses Androguard for this
 
-tree.py
 contains the code which builds a tree based on the tracking process, this is later used to generate an html page
