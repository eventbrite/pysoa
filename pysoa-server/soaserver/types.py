import attr


@attr.s(frozen=True)
class Error(object):
    code = attr.ib()
    message = attr.ib()
    field = attr.ib()


@attr.s
class ActionResponse(object):
    action = attr.ib()
    errors = attr.ib()
    body = attr.ib()


@attr.s
class JobResponse(object):
    errors = attr.ib()
    actions = attr.ib(default=[])
