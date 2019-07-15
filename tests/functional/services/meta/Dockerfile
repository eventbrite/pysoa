FROM pysoa-test-service

COPY tests/functional/services/meta /srv/meta/
RUN pip install -e /srv/meta

CMD ["/usr/local/bin/meta_service", "-s", "meta_service.settings", "--use-file-watcher", "meta_service,pysoa"]
