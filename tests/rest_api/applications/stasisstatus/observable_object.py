#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append("lib/python")
sys.path.append("tests/rest_api/applications")

LOGGER = logging.getLogger(__name__)

class ObservableObject(object):
    """Definition for an observable object."""

    def __init__(self, name, events):
        """Constructor.

        Keyword Arguments:
        name        -- The name of this ObservableObject.
        events      -- The events available for observing.
        """

        self.__name = name
        self.__registrar = dict()
        self.__suspended = 0

        for event in events:
            self.__registrar[event] = list()

    def __format__(self, format_spec):
        """Overrides default format handling for 'self'."""

        return self.__class__.__name__ + '[' + self.name + ']:'

    def activate(self):
        """Activates the object notification system."""

        self.__suspended = 0

    def notify_observers(self, event, message, notify_on_suspend=False):
        """Starts the chain of invocations for the callbacks.

        Keyword Arguments:
        event                  -- The list of callbacks to invoke.
        message                -- The event payload.
        notify_on_suspend      -- Whether or not to override suspended
                                  notifications (optional) (default False).

        Raises:
        ValueError
        """

        msg = '{0} '.format(self)

        if self.suspended and not notify_on_suspend:
            LOGGER.debug(msg + " Suspended; cannot notify observers.")
            return

        if not self.__validate(event=event):
            error = msg + 'Could not notify observers; Validation failed.'
            raise ValueError(error)

        for callback in self.__registrar[event]:
            LOGGER.debug(msg + 'Invoking {0}'.format(callback))
            callback(self, message)
        return

    def reset_registrar(self):
        """Resets the registrar to its initial, empty state.

        Note: This will reset the entire observer registrar.
        """

        msg = '{0} '.format(self)

        LOGGER.debug(msg + 'Resetting the observer registrar')
        for event in self.__registrar:
            del self.__registrar[event][:]
        LOGGER.debug(msg + 'Reset the observer registrar.')
        return

    def register_observers(self, event, observers):
        """Registers an observer with the list of observers.

        Keyword Arguments:
        event                  -- The event to observe.
        observers              -- A list of callable observers or a single
                                  callable observer.

        Raises:
        TypeError
        ValueError
        """

        msg = '{0} '.format(self)
        error = msg + 'Could not register observers'

        if not self.__validate(event=event):
            error += '; Validation failed.'
            raise ValueError(error)
        elif observers is None:
            error += 'for event [{0}]; [Observers] is None.'.format(event)
            raise ValueError(error)

        cache = list()
        if callable(observers):
            cache.append(observers)
        elif isinstance(observers, list):
            cache.extend(observers)
        else:
            msg += 'Cannot register observer {0} with registrar; [{1}] \
                    is an unsupported type.'
            raise TypeError(msg.format(observers,
                                       observers.__class__.__name__))

        if self.__registrar[event] is None:
            msg += 'Instantiating the observers for event {0}.'.format(event)
            LOGGER.debug(msg)
            self.__registrar[event] = list()
        self.__registrar[event].extend(cache)
        return

    def resume(self):
        """Resumes monitoring."""

        if self.__suspended < 0:
            self.__suspended = 0

        else:
            self.__suspended -= 1

    def suspend(self):
        """Suspends monitoring."""

        self.__suspended += 1

    def __validate(self, **kwargs):
        """Validates the parameters for value.

        If any of the parameters fails validation, an entry will be added to
        the log and processing will not continue.

        kwargs                 -- A dictionary containing the function
                                  parameters to validate.

        Returns:
        True if the parameters are valid, False otherwise.
        """

        valid = None
        error = '{0} Cannot continue; '.format(self)

        try:
            for arg in kwargs:
                value = kwargs[arg]
                if not value:
                    valid = False
                    reason = 'No value provided for [%r]' % arg
                    LOGGER.warn(error + reason)
                elif arg.lower() == 'event':
                    if value not in self.__registrar:
                        valid = False
                        reason = 'Registrar does not contain an entry for the \
                                  event [{1}]'.format(value)
                        LOGGER.warn(error + reason)
        except IndexError:
            LOGGER.warn(error + 'Validation failed due to IndexError.')
            valid = False

        return valid if valid is not None else True

    @property
    def name(self):
        """The friendly name for this instance."""

        return self.__name

    @property
    def suspended(self):
        """Flag indicating that the scenario is being torn down."""

        return self.__suspended > 0