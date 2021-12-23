import inspect
from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Dict, Generic, List, Tuple, TypeVar
from warnings import warn

from checkpointing.exceptions import CheckpointNotExist, ExpensiveOverheadWarning
from checkpointing.util.timing import Timer, timed_run
from checkpointing.decorator.typing import ReturnValue, Identifier
from checkpointing.decorator.context import Context


class DecoratorCheckpoint(ABC, Generic[ReturnValue]):
    """The base class for any decorator checkpoints."""

    def __init__(self, error: str = "warn") -> None:
        """
        Args:
            error: the behavior when retrieval or saving raises unexpected exceptions
                (exceptions other than checkpointing.CheckpointNotExist).
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
                res, run_time = timed_run(func, args, kwargs)
                self.__warn_if_more_expensive(retrieve_time, run_time)
                self._call_save(res)
            return res

        return inner

    def __warn_if_more_expensive(self, retrieve_time: float, run_time: float) -> None:
        """
        Warn the user if retrieval takes longer than running the function.

        Args:
            retrieve_time: time for retrieving the cached result
            run_time: time for running the function
        """
        if retrieve_time > run_time:
            warn(
                f"The overhead for checkpointing '{self.__context.function_name}' takes more time than the function call itself "
                f"({retrieve_time:.2f}s > {run_time:.2f}s). "
                "Consider optimize the checkpoint or just remove it, and let the function execute every time.",
                category=ExpensiveOverheadWarning,
                stacklevel=3,
            )

    @abstractmethod
    def retrieve(self, context: Context) -> ReturnValue:
        """
        Retrieve the data based on the function call context.
        If the there is no corresponding previously saved results, raise a `checkpointing.CheckpointNotExist`.

        Args:
            context: Context of the function call

        Returns:
            The retrieved return value of the function call.
        """
        pass

    def _call_retrieve(self) -> ReturnValue:
        """
        Call `self.retrieve()` with correct parameters.

        Overwrite this method to create abstract subclasses that needs different parameters for retrieving the result.
        """
        return self.retrieve(self.__context)

    def __timed_tentative_retrieve(self) -> Tuple[bool, ReturnValue, float]:
        """
        Retrive the data based on the function call context tentatively,
        tracking the time and capturing the checkpointing.exceptions.CheckpointNotExist error.

        Returns:
            A tuple of three elements:
            - bool: whether the retrival succeeds or not
            - ReturnValue: the extracted return value, if successful, otherwise None
            - float: the time (seconds) it takes to retrieve
        """

        timer = Timer().start()
        try:
            res = self._call_retrieve()
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

    def _call_save(self, result: ReturnValue) -> None:
        """
        Call `self.save()` with correct parameters.

        Overwrite this method to create abstract subclasses that needs different parameters for saving the result.
        """
        return self.save(self.__context, result)


class HashDecoratorCheckpoint(DecoratorCheckpoint, Generic[Identifier]):
    """
    Checkpoint that (conceptually) hash the context to a unique identifier,
    and use the identifier for the retrieval and saving.
    """

    @abstractmethod
    def hash(self, context: Context) -> Identifier:
        """
        Hash the function call context into a unique identifier.
        The identifier should encode any information that determines what the return value would be.

        Args:
            context: function call context

        Returns:
            A unique identifier for the function call.
            This will be used to retrive/save the function call result.
        """
        pass

    @abstractmethod
    def retrieve(self, identifier: Identifier) -> ReturnValue:
        """
        Retrieve the data based on the identifier.
        If the there is no corresponding previously saved results, raise a `checkpointing.CheckpointNotExist`.

        Args:
            identifier: Identifier of the function call

        Returns:
            The retrieved return value of the function call.
        """
        pass

    def _call_retrieve(self) -> ReturnValue:
        """
        Call self.retrieve() with the identifier.
        """
        id = self.identify(self.__context)
        return self.retrieve(id)

    @abstractmethod
    def save(self, identifier: Identifier, result: ReturnValue) -> None:
        """
        Save the result of the function based on the identifier.

        Args:
            identifier: Identifier of the function call
            result: Return value of the function call
        """
        pass

    def _call_save(self, result: ReturnValue) -> None:
        """
        Call self.save() with the identifier
        """
        id = self.identify(self.__context)
        self.save(id, result)
