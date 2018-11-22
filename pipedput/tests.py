class AbstractTest:
    def __call__(self, event):
        raise NotImplementedError()

    def __or__(self, other):
        return _OrTest(self, other)

    def __and__(self, other):
        return _AndTest(self, other)


class _OperatorTest(AbstractTest):
    def __init__(self, first_test, second_test):
        self.first_test = first_test
        self.second_test = second_test


class _OrTest(_OperatorTest):
    def __call__(self, event):
        return self.first_test(event) or self.second_test(event)


class _AndTest(_OperatorTest):
    def __call__(self, event):
        return self.first_test(event) and self.second_test(event)


class CallbackTest(AbstractTest):
    """ only process the event if the callback returned True """
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def __call__(self, event):
        return bool(self.callback(event)) is True


class RequireProject(AbstractTest):
    """ only process the event if the project matches the provided name """
    def __init__(self, name) -> None:
        """
        :param name: the project name with it’s namespace. Something like 'foo/bar'
        """
        super().__init__()
        self.name = name

    def __call__(self, event):
        return event['project']['path_with_namespace'] == self.name


class RequireTag(AbstractTest):
    """ only process the event if the pipeline is executed for a tag """
    def __call__(self, event):
        return event['object_attributes']['tag'] is True


class RequireSuccess(AbstractTest):
    """ only process the event if the pipeline was successful """
    def __call__(self, event):
        return event['object_attributes']['status'] == 'success'
