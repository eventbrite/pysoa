FROM pysoa-test-service

COPY tests/functional/services/user /srv/user/
RUN pip install -e /srv/user

ENV DJANGO_SETTINGS_MODULE=user_service.settings

RUN echo 'django-admin migrate\n\
' > /usr/local/bin/pysoa-startup-processes.sh

CMD ["/usr/local/bin/user_service", "-f", "4"]
