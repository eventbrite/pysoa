FROM pysoa-test-service

COPY tests/functional/services/echo /srv/echo/
RUN pip install -e /srv/echo

# We install PyInotify in just this service so we can have coverage of polling- and PyInotify-based file watching
RUN pip install pyinotify

CMD ["/usr/local/bin/echo_service", "-s", "echo_service.settings", "-f", "3", "--use-file-watcher", "echo_service,pysoa"]
