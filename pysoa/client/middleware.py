class ClientMiddleware(object):

    def process_job_request(self, request_id, meta, job_request):
        """
        Process a job request before it is sent by the Client.

        Args:
            request_id: int
            meta: transport metadata dict
            job_request: JobRequest dict

        Returns:
            None
        """
        pass

    def process_job_response(self, request_id, meta, job_response):
        """
        Process a job response after it is received by the Client.

        Args:
            request_id: int
            meta: transport metadata dict
            job_request: JobRequest dict

        Returns:
            None
        """
        pass
