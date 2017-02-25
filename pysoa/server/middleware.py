class ServerMiddleware(object):
    def process_job_request(self, job_request):
        """
        Process JobRequest messages before they are run by the Server.

        Args:
            job_request: a JobRequest dictionary.

        Returns:
            None
        """
        pass

    def process_action_request(self, action_request):
        """
        Process ActionRequest messages before they are run by the Server.

        Args:
            action_request: a ActionRequest dictionary.

        Returns:
            None
        """
        pass

    def process_action_response(self, action_response):
        """
        Process ActionResponse messages before they are appended to the
        JobResponse message.

        Args:
            action_response: a ActionResponse dictionary.

        Returns:
            None
        """
        pass

    def process_job_response(self, job_response):
        """
        Process JobResponse messages before they sent to the Client.

        Args:
            job_resposne: a JobResponse dictionary.

        Returns:
            None
        """
        pass
