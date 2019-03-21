from typing import Callable


class AbstractConstraint:
    def __call__(self, event):
        raise NotImplementedError()

    def __or__(self, value):
        return _Or(self, value)

    def __and__(self, value):
        return _And(self, value)


class AbstractOperator(AbstractConstraint):
    def __init__(self, first_operand, second_operand):
        self.first_operand = first_operand
        self.second_operand = second_operand


class _And(AbstractOperator):
    def __call__(self, value):
        return self.first_operand(value) and self.second_operand(value)


class _Or(AbstractOperator):
    def __call__(self, value):
        return self.first_operand(value) or self.second_operand(value)


class Callback(AbstractConstraint):
    """ only process the event if the callback returned True """
    def __init__(self, callback: Callable, expect: bool = True) -> None:
        """
        :param callback: the callable to execute when evaluating the constraint
        :param expect: the boolean value that is expected to be returned
        """
        super().__init__()
        self.callback = callback
        self.expect = expect

    def __call__(self, event):
        return bool(self.callback(event)) is self.expect


class RequireProject(AbstractConstraint):
    """ only process the event if the project matches the provided name """
    def __init__(self, name) -> None:
        """
        :param name: the project name with it’s namespace. Something like 'foo/bar'
        """
        super().__init__()
        self.name = name

    def __call__(self, event):
        return event['project']['path_with_namespace'] == self.name


class RequireTag(AbstractConstraint):
    """ only process the event if the pipeline is executed for a tag """
    def __call__(self, event):
        return event['object_attributes']['tag'] is True


class RequireSuccess(AbstractConstraint):
    """ only process the event if the pipeline was successful """
    def __call__(self, event):
        return event['object_attributes']['status'] == 'success'
