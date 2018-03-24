#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""
import logging
import sys
import cgi
import re

from twisted.internet import reactor
from twisted.internet import error
from twisted.web.server import Site
from twisted.web.resource import Resource, NoResource

LOGGER = logging.getLogger(__name__)

THIS_MODULE = sys.modules[__name__]


class RealtimeData(object):
    """This class holds all of the data that is being stored in realtime. The
    class cotains a dictionary of "tables" at the top level keyed on the
    table's name. Each table consists of "rows" represented by a list of
    dictionaries.

    All variables are stored as strings since that is how they get passed in by
    Asterisk and that is the format in which they are returned to Asterisk.
    This means that type-checking on this sort of realtime backend is non-
    existent, but since this is only being used in a test environment, I don't
    care.
    """
    def __init__(self):
        self.tables = {}

    def add_rows(self, table_name, rows):
        """Add multiple rows to a table.

        :param table_name: String representing table to update.
        :param rows: List of dictionaries to add to the table.
        """
        try:
            self.tables[table_name].extend(rows)
        except KeyError:
            self.tables[table_name] = rows

    def add_row(self, table_name, row):
        """Add a single row to a table.

        :param table_name: String representing table to update.
        :param row: Dictionary to add to the table.
        """
        self.add_rows(table_name, [row])

    def retrieve_row(self, table_name, where):
        """Retrieve a single row from a table.

        :param table_name: String representing table to update.
        :param where: Dictionary used to determine which row to retrieve.

        :returns: Row which matches the given input. If multiple rows match,
        then only the first is returned. If no rows match, an empty row is
        returned.

        :raises: KeyError if a table does not exist with name table_name.
        """
        rows = self.retrieve_rows(table_name, where)
        if rows:
            LOGGER.debug("Retrieved rows %s" % rows)
            return rows[0]
        else:
            return {}

    def _filter_rows(self, table, where):
        """Internal method used to determine rows affected by an operation

        :param table: The table on which to apply the where clause (not the
         table name).
        :param where: A dictionary of key/value pairs used to filter rows from
         the table.
        :returns: A list of rows that match the given input.

        If a value is empty in the where clause, then it matches all rows in
        the table that have the specified key.
        """
        LOGGER.debug("Table has %s" % table)
        LOGGER.debug("Searching table for %s" % where)

        return [row for row in table
                if all(key in row and re.match(value, row[key])
                       for key, value in where.items())]

    def retrieve_rows(self, table_name, where):
        """Retrieve multiple rows from a table.

        :param table_name: String representing table to update.
        :param where: Dictionary that determines which rows to retrieve.
        :returns: List of rows that match the given input.
        :raises: Keyerror if a table does not exist with name table_name
        """
        return self._filter_rows(self.tables[table_name], where)

    def update_rows(self, table_name, where, update):
        """Update row data in a table.

        :param table_name: String representing table to update.
        :param where: Dictionary that determines which rows to update.
        :param update: Dictionary with new values to apply to affected rows.
        :returns: number of rows that have been updated.
        :raises: KeyError if a table does not exist with name table_name.
        """
        to_update = self._filter_rows(self.tables[table_name], where)

        for item in to_update:
            item.update(update)

        LOGGER.debug("After update, table has %s" % self.tables[table_name])

        return len(to_update)

    def delete_rows(self, table_name, where):
        """Delete rows from a table.
        :param table_name: String representing table to delete from.
        :param where: Dictionary that determines which rows to delete.
        :returns: number of rows deleted.
        :raises: KeyError if a table does not exist with name table_name.
        """
        LOGGER.debug("Being told to remove where %s" % where)
        to_delete = self._filter_rows(self.tables[table_name], where)
        LOGGER.debug("Items to delete are %s" % to_delete)
        self.tables[table_name] = [row for row in self.tables[table_name]
                                   if row not in to_delete]
        return len(to_delete)


class RootResource(Resource):
    """Resource provided by the root of our HTTP server.
    """
    def __init__(self, rt_data):
        Resource.__init__(self)
        self.rt_data = rt_data
        LOGGER.debug("Creating RootResource")

    def getChild(self, name, request):
        """Get child resource for site root.
        :param name: Name of requested child resource.
        :param request: incoming HTTP request.
        :returns: Table resource for the given name.

        When Asterisk makes an HTTP request, Twisted will initially call into
        this resource in order to be given the proper resource given the path
        in the URL. The name requested is expected to be one of the realtime
        tables, so we create a TableResource representing that table. The
        TableResource is then called into to get the resource relating to the
        operation to perform on the table.
        """
        LOGGER.debug("Asking root for child %s", name)
        return TableResource(name, self.rt_data)


class TableResource(Resource):
    """Resource for a specific table on our HTTP server.
    """
    def __init__(self, table_name, rt_data):
        Resource.__init__(self)
        self.table_name = table_name
        self.rt_data = rt_data
        LOGGER.debug("Creating TableResource for %s", table_name)

    def getChild(self, name, request):
        """Get child resource for a table
        :param name: Name of requested child resource.
        :param request: Incoming HTTP request.
        :returns: LeafResource subclass.

        Twisted automatically calls this when trying to get a requested
        resource. The expected names of the resources are one of

        * single
        * multi
        * update
        * store
        * destroy
        * require
        * static

        Each of these corresponds to a resource class in this module. We use
        reflection here to generate the requested resource dynamically. Each of
        these resources represents an operation to perform on the table.
        """
        try:
            return getattr(THIS_MODULE, "_" + name + "Resource")(
                self.table_name, self.rt_data
            )
        except AttributeError as ex:
            msg = "Error retrieving resource %s/%s: %s" % \
                (self.table_name, name, ex)
            LOGGER.error(msg)
            return NoResource(message=msg)


class LeafResource(Resource):
    """Base class for leaf resources.

    A leaf resource is one that has the isLeaf property set. This means that
    there are no children for this resource in the hierarchy.

    All resources representing table operations are subclasses of this
    LeafResource since they all have no child resources. The LeafResource class
    provides common operations that its children require, mostly pertaining to
    manipulation of request data.
    """
    isLeaf = True

    def __init__(self, table_name, rt_data):
        Resource.__init__(self)
        self.table_name = table_name
        self.rt_data = rt_data
        LOGGER.debug("Constructing LeafResource")

    def unpack_args(self, args):
        """Unpack lists used a args values.
        :param args: Dictionary of key-list pairs to unpack
        :returns: Same dictionary with values unpacked

        A request object presents the URL and POST parameters as a dictionary
        of the form {'param_name': [values]}. The values are placed in a list
        to accommodate repeated parameter names that may appear in requests.
        Since Asterisk does not repeat parameters, we are safe to unpack the
        list.

        Example input: {'foo': ['cat'], 'bar': ['dog']}
        Example output: {'foo': 'cat', 'bar': 'dog'}

        This method would be more efficient if we were using Python 2.7+
        since we could use a dict comprehension.
        """
        filtered_args = {}
        for key, values in args.items():
            if " LIKE" in key:
                # Strip away " LIKE" and % from values
                filtered_args[key[:-5]] = [val.replace('%', '.*')
                                           for val in values]
            else:
                filtered_args[key] = values

        LOGGER.debug('filtered args is %s' % filtered_args)

        return dict((key, values[0] if values else '.*') for key, values in
                    filtered_args.items())

    def encode_row(self, row):
        """Encode a retrieved row for an HTTP response.
        :param row: Dictionary to format for HTTP response body.
        :returns: String of key=values.

        Example input: {'foo': 'cat, 'bar': 'dog', 'baz: 'donkey'}
        Example output: 'foo=cat&bar=dog&baz=donkey'
        """
        string = '&'.join(['{0}={1}'.format(cgi.escape(key), cgi.escape(val))
                           for key, val in row.items()])
        LOGGER.debug("Returning response %s" % string)
        return string

    def encode_multi_row(self, rows):
        """Encode multiple rows for an HTTP response.
        :param rows: List of dictionaries to encode in HTTP response body.
        :returns: Encoded rows, each row separated by a carriage return line
         feed.
        """
        string = '\r\n'.join([self.encode_row(row) for row in rows])
        LOGGER.debug("Returning response %s" % string)
        return string

    def return_404(self, request):
        """Return a 404 HTTP response.
        :param request: The request to which we are responding.
        :returns: NoResource's rendering of the request.

        Performed if a request tries to access a nonexistent table.
        """
        page = NoResource(message="Table %s could not be found" %
                          self.table_name)
        return page.render(request)


class _singleResource(LeafResource):
    """Resource for retrieving single record.

    This retrieves a single row of data from the
    realtime data.
    """
    def render_POST(self, request):
        """Handle the POST method.
        :param request: HTTP POST request.
        :returns: Single encoded row of data.

        POST parameters are used to determine which row to retrieve from the
        database.
        """
        LOGGER.debug("Asked to render_POST in the single resource")
        LOGGER.debug("request.args is %s" % request.args)
        try:
            return self.encode_row(self.rt_data.retrieve_row(self.table_name,
                                   self.unpack_args(request.args)))
        except KeyError:
            return self.return_404(request)


class _multiResource(LeafResource):
    """Resource for retrieving multiple records.

    This retrieves multiple rows of data from the realtime data.
    """
    def render_POST(self, request):
        """Handle the POST method.
        :param request: HTTP POST request.
        :returns: Multiple encoded rows.

        POST parameters are used to determine which rows to retrieve from the
        realtime data.

        This is an abstraction where Asterisk does a poor job of being
        amenable to non-database sources. Sending parameters like
        "id LIKE=%" means we have some work cut out for us in order to be able
        to successfully retrieve values.
        """
        # If this were python 2.7+ we could use a dict comprehension here
        LOGGER.debug("Asked to render POST on the multi resource")
        LOGGER.debug("Multi URI: %s" % request.uri)
        try:
            return self.encode_multi_row(
                self.rt_data.retrieve_rows(self.table_name,
                                           self.unpack_args(request.args)))
        except KeyError:
            return self.return_404(request)


class _updateResource(LeafResource):
    """Resource for updating records.
    """
    def render_POST(self, request):
        """Handle the POST method.
        :param request: HTTP POST request.
        :returns: The number of rows updated by the request.

        The URL parameters determine which objects to update, and the POST
        parameters determine which object fields to update.

        Twisted makes this a bit difficult since it combines the URL and POST
        parameters into a single dictionary. So what we have to do is parse the
        URL parameters out of the URL and then remove those from the dictionary
        that Twisted gives us. With the parameters separated out, the update
        operation can proceed.
        """
        LOGGER.debug("Asked to render POST in the update resource")

        _, _, uri_params = request.uri.rpartition('?')
        # The odd slice notation gets the first and third items from the tuple
        # returned from item.partition
        uri_args = dict(item.partition('=')[::2] for item in
                        uri_params.split('&'))

        # The dict() created as the argument to unpack args is essentially the
        # set difference between request.args and uri_args.
        post_args = self.unpack_args(dict((key, request.args[key])
                                     for key in request.args
                                     if key not in uri_args))

        LOGGER.debug("URI args: %s" % uri_args)
        LOGGER.debug("POST args: %s" % post_args)
        try:
            affected = self.rt_data.update_rows(self.table_name, uri_args,
                                                post_args)
        except KeyError:
            return self.return_404(request)
        else:
            return str(affected)


class _storeResource(LeafResource):
    """Resource for handling storing into realtime
    """
    def render_POST(self, request):
        """Handle HTTP POST.
        :param request: Incoming HTTP POST.
        :returns: "1"

        This is supposed to return the number of rows inserted, but since this
        is only ever used to insert a single row, and insertion never fails,
        this always returns "1".
        """
        LOGGER.debug("Asked to render POST in the store resource")
        self.rt_data.add_row(
            self.table_name, self.unpack_args(request.args)
        )
        return "1"


class _destroyResource(LeafResource):
    """Resource for handling destroying realtime data
    """
    def render_POST(self, request):
        """Handle HTTP POST.
        :param request: Incoming HTTP POST.
        :returns: the number rows deleted.
        """
        LOGGER.debug("Asked to render POST in the destroy resource")
        try:
            affected = self.rt_data.delete_rows(
                self.table_name, self.unpack_args(request.args)
            )
        except KeyError:
            return self.return_404(request)
        else:
            return str(affected)


class _requireResource(LeafResource):
    """Resource for handling realtime requirements
    """
    def render_GET(self, request):
        """Handle HTTP GET.
        :param request: Incoming HTTP GET.
        :returns: "0"

        This is used to determine if the types being used for specific
        realtime fields are correct. Since we store everything as a string, we
        don't really care and rely on user input to store types that make sense
        for the given tables. Returning a "0" body indicates we satisfy all
        requirements.
        """
        return "0"


class _staticResource(LeafResource):
    """Resource used for static realtime.
    """
    def render_GET(self, request):
        """Handle HTTP GET.
        :param request: Incoming HTTP GET.
        :returns: All matching records

        Filename is passed in as URL parameter.
        """
        LOGGER.debug("Asked to render GET in the static resource")
        # Forego a more complicated unpack since the file is the only thing we
        # care about
        where = {'filename': request.args['file'][0], 'commented': '0'}
        try:
            return self.encode_multi_row(
                self.rt_data.retrieve_rows(self.table_name, where)
            )
        except KeyError:
            return self.return_404(request)


class RealtimeTestModule(object):
    """Test module for realtime database tests.

    This module uses an HTTP server to listen for requests in order to retrieve
    or modify stored data. The actual data being retrieved is stored in an
    instance of the RealtimeData class.
    """
    def __init__(self, module_config, test_object):
        self.test_object = test_object
        self.module_config = module_config
        self.rt_data = RealtimeData()
        self.test_object.register_ami_observer(self._ami_connect)

        self.populate_rt_data(module_config.get('data'))
        self.setup_http()

    def populate_rt_data(self, data):
        """Populate the database with an initial set of data.
        :data: yaml dictionary that mimicks the RealtimeData format
        """
        if not data:
            return

        for table_name, rows in data.items():
            self.rt_data.add_rows(table_name, rows)

    def setup_http(self):
        """Create Twisted HTTP server.

        We supply Twisted with a root resource to call into for all HTTP
        requests made. The root resource is then responsible for dynamically
        creating resources to handle specific requests
        """
        resource = RootResource(self.rt_data)
        factory = Site(resource)
        reactor.listenTCP(46821, factory)

    def _ami_connect(self, ami):
        """Callback for when AMI connects.

        This is the launching point for the actual meat of each test. This
        calls into a configuration-specified method, supplying the realtime
        data.
        """
        if 'entry_method' not in self.module_config or \
                'entry_module' not in self.module_config:
            return

        module = __import__(self.module_config['entry_module'])
        method = getattr(module, self.module_config['entry_method'])
        method(self.rt_data, self.test_object, ami)
