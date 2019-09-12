FROM pysoa-test-service

COPY tests/functional/services/echo /srv/echo/
RUN pip install -e /srv/echo

# We install PyInotify in just this service so we can have coverage of polling- and PyInotify-based file watching
RUN pip install pyinotify

# We start this one differently from the other containers so that we can confirm that both permitted approaches --
# the entry-point binary and `-m module_name` - pass the double-import trap detection.
CMD ["-m", "echo_service.standalone", "-s", "echo_service.settings", "-f", "3", "--use-file-watcher", "echo_service,pysoa"]
