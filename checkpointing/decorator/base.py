import inspect
from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Dict, List, TypeVar, Tuple
from warnings import warn

from checkpointing.exceptions import CheckpointNotExist, ExpensiveOverheadWarning
from checkpointing.util.timing import Timer

ReturnValue = TypeVar("ReturnValue")
"""
Return value of the function
"""


class Context:
    """
    Context providing information for a function call.
    """

    def __init__(self, func, args, kwargs) -> None:
        """
        Args:
            args: the non-keywords arguments of the function call
            kwargs: the keyword arguments of the function call
            func: the function object that is being called
        """

        self.__func: Callable[..., ReturnValue] = func
        """Function called"""

        self.__args: List = args
        """Arguments of the function call"""

        self.__kwargs: Dict = kwargs
        """Keyword arguments of the function call"""

        self.__signature = inspect.signature(self.__func)
        """Signature of the function"""

    @property
    def arguments(self):
        args = self.__signature.bind(*self.__args, **self.__kwargs)
        args.apply_defaults()
        return args.arguments

    @property
    def function_name(self):
        return self.__func.__name__


class DecoratorCheckpoint(ABC):
    """The base class for any decorator checkpoints."""

    def __init__(self, error: str = "warn") -> None:
        """
        Args:
            error: the behavior when identification, saving, or retrieval raises unexpected exceptions (exceptions other than `CheckpointNotExist`).
                Could be:
                - `"raise"`, the exception will be raised.
                - `"warn"`, a warning will be issued to inform that the checkpointing task has failed.
                    But the user function will be invoked and executed as if it wasn't checkpointed.
                - `"ignore"`, the exception will be ignored and the user function will be invoked and executed normally.
        """

        self.__error: str = error
        """The behavior when identification, saving or retrieval raises unexpected exceptions."""

        self.__context: Context = None
        """The context of the latest function call"""

    def __call__(self, func: Callable[..., ReturnValue]) -> Callable[..., ReturnValue]:
        """Magic method invoked when used as a decorator."""

        @wraps(func)
        def inner(*args, **kwargs) -> ReturnValue:
            self.__context = Context(func, args, kwargs)

            retrieve_success, res, retrieve_time = self.__timed_tentative_retrieve()
            if retrieve_success:
                return res
            else:
                res, run_time = self.__timed_run(func, args, kwargs)
                self.__warn_if_more_expensive(retrieve_time, run_time)
                self.save(self.__context, res)
            return res

        return inner

    def __timed_run(self, func: Callable[..., ReturnValue], args: Tuple, kwargs: Dict) -> Tuple[ReturnValue, float]:
        """
        Run the function with the arguments, recording the run time.
        """
        t = Timer().start()
        res = func(*args, **kwargs)
        return res, t.time

    def __warn_if_more_expensive(self, retrieve_time, run_time):
        if retrieve_time >= run_time:
            warn(
                f"The overhead for checkpointing function <{self.__context.function_name}> takes more time than the function call itself "
                f"({retrieve_time:.2f} > {run_time:.2f}). "
                "Consider optimize the retrieval process or just remove the checkpoint, to let the function run every time.",
                category=ExpensiveOverheadWarning,
                stacklevel=3,
            )

    @abstractmethod
    def retrieve(self, context: Context) -> ReturnValue:
        """
        Retrieve the data based on the function call context.
        If the there is no corresponding previously saved results, raise a `checkpointing.exceptions.CheckpointNotExist`.

        Args:
            context: Context of the function call

        Returns:
            The retrieved return value of the function call.
        """
        pass

    def __timed_tentative_retrieve(self) -> Tuple[bool, ReturnValue, float]:
        """
        Retrive the data based on the function call context tentatively,
        tracking the time and capturing the `CheckpointNotExist` error.

        Returns:
            A tuple of three elements:
            - bool: whether the retrival succeeds or not
            - ReturnValue: the extracted return value, if successful, otherwise None
            - float: the time (seconds) it takes to retrieve
        """

        timer = Timer().start()
        try:
            res = self.retrieve(self.__context)
            return True, res, timer.time
        except CheckpointNotExist:
            return False, None, timer.time

    @abstractmethod
    def save(self, context: Context, result: ReturnValue) -> None:
        """
        Save the result for the function call context.

        Args:
            context: Context of the function call
        """
        pass

    def __time_aware_rerun_save(self):
        """
        Re-run the function and
        """
