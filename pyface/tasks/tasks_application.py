# Copyright (c) 2014-2016 by Enthought, Inc., Austin, TX
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD
# license included in enthought/LICENSE.txt and may be redistributed only
# under the conditions described in the aforementioned license.  The license
# is also available online at http://www.enthought.com/licenses/BSD.txt
# Thanks for using Enthought open source!
""" Define a base Task application class to create the event loop, and launch
the creation of tasks and corresponding windows.
"""

from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

from functools import partial
import logging

from traits.api import (
    Callable, HasStrictTraits, List, Instance, Property, Str, Unicode,
    cached_property, on_trait_change
)

from pyface.gui_application import GUIApplication

logger = logging.getLogger(__name__)


class TaskFactory(HasStrictTraits):
    """ A factory for creating a Task with some additional metadata.
    """

    #: The task factory's unique identifier. This ID is assigned to all tasks
    #: created by the factory.
    id = Str

    #: The task factory's user-visible name.
    name = Unicode

    #: A callable with the following signature:
    #:
    #:     callable(**traits) -> Task
    #:
    #: Often this attribute will simply be a Task subclass.
    factory = Callable

    def create(self, **traits):
        """ Creates the Task.

        The default implementation simply calls the 'factory' attribute.
        """
        return self.factory(**traits)


class TasksApplication(GUIApplication):
    """ A base class for Pyface tasks applications.
    """

    # -------------------------------------------------------------------------
    # 'TaskApplication' interface
    # -------------------------------------------------------------------------

    # Task management --------------------------------------------------------

    #: List of all running tasks
    tasks = List(Instance("pyface.tasks.task.Task"))

    #: Currently active Task if any.
    active_task = Property(depends_on='active_window.active_task')

    #: List of all application task factories.
    task_factories = List()

    #: The default layout for the application. If not specified, a single
    #: window will be created with the first available task factory.
    default_layout = List(
        Instance('pyface.tasks.task_window_layout.TaskWindowLayout')
    )

    #: Hook to add global schema additions to tasks/windows
    extra_actions = List(
        Instance('pyface.tasks.action.schema_addition.SchemaAddition')
    )

    #: Hook to add global dock pane additions to tasks/windows
    extra_dock_pane_factories = List(Callable)

    # Window lifecycle methods -----------------------------------------------

    def create_task(self, id):
        """ Creates the Task with the specified ID.

        Parameters
        ----------
        id : str
            The id of the task factory to use.

        Returns
        -------
        The new Task, or None if there is not a suitable TaskFactory.
        """
        factory = self._get_task_factory(id)
        if factory is None:
            logger.warning("Could not find task factory {}".format(id))
            return None

        task = factory.create(id=factory.id)
        task.extra_actions.extend(self.extra_actions)
        task.extra_dock_pane_factories.extend(self.extra_dock_pane_factories)
        return task

    def create_window(self, layout=None, **kwargs):
        """ Connect task to application and open task in a new window.

        Parameters
        ----------
        layout : TaskLayout instance or None
            The pane layout for the window.
        **kwargs : dict
            Additional keyword arguments to pass to the window factory.


        Returns
        -------
        window : ITaskWindow instance or None
            The new TaskWindow.
        """
        from pyface.tasks.task_window_layout import TaskWindowLayout

        window = super(TasksApplication, self).create_window()

        if layout is not None:
            for task_id in layout.get_tasks():
                task = self.create_task(task_id)
                if task is not None:
                    window.add_task(task)
                else:
                    msg = 'Missing factory for task with ID %r'
                    logger.error(msg, task_id)
        else:
            # Create an empty layout to set default size and position only
            layout = TaskWindowLayout()

        window.set_window_layout(layout)

        return window

    def _create_windows(self):
        """ Create the initial windows to display from the default layout.
        """
        for layout in self.default_layout:
            self.active_window = self.create_window(layout)

    # -------------------------------------------------------------------------
    # Private interface
    # -------------------------------------------------------------------------

    def _get_task_factory(self, id):
        """ Returns the TaskFactory with the specified ID, or None.
        """
        for factory in self.task_factories:
            if factory.id == id:
                return factory
        return None

    # Destruction utilities ---------------------------------------------------

    @on_trait_change('windows:closed')
    def _on_window_closed(self, window, trait, old, new):
        """ Listener that ensures window handles are released when closed.
        """
        if getattr(window, 'active_task', None) in self.tasks:
            self.tasks.remove(window.active_task)
        super(TasksApplication,
              self)._on_window_closed(window, trait, old, new)

    # Trait initializers and property getters ---------------------------------

    def _window_factory_default(self):
        """ Default to TaskWindow.

        This will be sufficient in many cases as customized behaviour comes
        from the Task and the TaskWindow is just a shell.
        """
        from pyface.tasks.task_window import TaskWindow
        return TaskWindow

    def _default_layout_default(self):
        from pyface.tasks.task_window_layout import TaskWindowLayout
        window_layout = TaskWindowLayout()
        if self.task_factories:
            window_layout.items = [self.task_factories[0].id]
        return [window_layout]

    def _extra_actions_default(self):
        """ Extra application-wide menu items

        This adds a collection of standard Tasks application menu items and
        groups to a Task's set of menus.  Whether or not they actually appear
        depends on whether the appropriate menus are provided by the Task.
        """
        from pyface.action.api import (
            AboutAction, CloseActiveWindowAction, ExitAction
        )
        from pyface.tasks.action.api import (
            DockPaneToggleGroup, SchemaAddition, TaskToggleGroup,
            TaskWindowToggleGroup
        )

        return [
            SchemaAddition(
                id='close_action',
                factory=partial(CloseActiveWindowAction, application=self),
                path='MenuBar/File/close_group',
            ),
            SchemaAddition(
                id='exit_action',
                factory=partial(ExitAction, application=self),
                path='MenuBar/File/close_group',
                absolute_position='last',
            ),
            SchemaAddition(
                id='TaskToggleGroup',
                factory=TaskToggleGroup,
                path='MenuBar/View'
            ),
            SchemaAddition(
                id='DockPaneToggleGroup',
                factory=DockPaneToggleGroup,
                path='MenuBar/View',
                after='TaskToggleGroup',
            ),
            SchemaAddition(
                id='TaskWindowToggleGroup',
                factory=partial(TaskWindowToggleGroup, application=self),
                path='MenuBar/Window'
            ),
            SchemaAddition(
                id='about_action',
                factory=partial(AboutAction, application=self),
                path='MenuBar/Help/about_group',
            ),
        ]

    @cached_property
    def _get_active_task(self):
        if self.active_window is not None:
            return getattr(self.active_window, 'active_task', None)
        else:
            return None