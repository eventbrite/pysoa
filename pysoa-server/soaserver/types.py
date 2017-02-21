import attr


@attr.s(frozen=True)
class Error(object):
    code = attr.ib()
    message = attr.ib()
    field = attr.ib()


@attr.s
class ActionRequest(object):
    action = attr.ib()
    body = attr.ib()
    switches = attr.ib()


@attr.s
class ActionResponse(object):
    action = attr.ib()
    errors = attr.ib(default=attr.Factory(list))
    body = attr.ib(default=None)


@attr.s
class JobResponse(object):
    errors = attr.ib(default=attr.Factory(list))
    actions = attr.ib(default=attr.Factory(list))
