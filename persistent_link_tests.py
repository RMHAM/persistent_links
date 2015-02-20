#!/usr/bin/env python
""" persistent_link_tests.py - Unit tests for the persistent_links.py script
"""
# persistent_link_tests.py - Script to test persistent links script on Free Star* (D-STAR) systems.
#    Copyright (C) 2015  Jim Schreckengast <n0hap@arrl.net>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Version 0.9

import nose
from nose.tools import raises
from mock import patch, Mock, sentinel, MagicMock, call
import persistent_links
import re
import os
import time
import sys
from StringIO import StringIO

GOOD_CONFIG_FILE = "# This is a good configuration file\n" \
                   "ADMIN=N0HAP"


# Older versions of nose do not have assert_dict_equal
def assert_dict_equal(d1, d2, msg=None):
    if not msg:
        msg = "%s != %s" % (d1, d2)
    if type(d1) is not dict:
        raise AssertionError(msg)
    if type(d2) is not dict:
        raise AssertionError(msg)
    if len(d1) != len(d2):
        raise AssertionError(msg)
    for k in d1.keys():
        if k not in d2 or d2[k] != d1[k]:
            raise AssertionError(msg)


# Older versions of nose do not have assert_list_equal
def assert_list_equal(l1, l2, msg=None):
    if not msg:
        msg = "%s != %s" % (l1, l2)
    if type(l1) is not list:
        raise AssertionError(msg)
    if type(l2) is not list:
        raise AssertionError(msg)
    if len(l1) != len(l2):
        raise AssertionError(msg)
    for item in l1:
        if item not in l2:
            raise AssertionError(msg)


# Older versions of nose do not have assert_regexp_matches
def assert_regexp_matches(value, pattern, msg=None):
    if not msg:
        msg = "%s !~ %s" % (value, pattern)
    if not re.search(pattern, value):
        raise AssertionError(msg)


def split_keeping_separator(txt, sep):
    # Can't use conditional expressions in Python 2.4
    # Equivalent of reduce(lambda acc, i: acc[:-1] + [acc[-1] + i] if i == sep else acc + [i],
    # re.split("(%s)" % re.escape(sep), txt), [])
    acc = []
    for item in re.split("(%s)" % re.escape(sep), txt):
        if item == sep:
            acc = acc[:-1] + [acc[-1] + item]
        else:
            acc += [item]
    return acc


def open_mock_iter(file_contents, side_effect=None):
    def decorator(func):
        @patch('__builtin__.open', create=True)  # required, since contexts are not available
        def wrapper(open_mock, *args, **kwargs):
            if side_effect:
                open_mock.side_effect = side_effect
            open_mock.return_value = MagicMock(spec=file)
            open_mock.return_value.__iter__.return_value = iter(split_keeping_separator(file_contents, "\n"))
            if hasattr(open_mock.return_value, '__enter__'):
                handle = open_mock.return_value.__enter__.return_value
                handle.__iter__.return_value = iter(split_keeping_separator(file_contents, "\n"))
            result = func(open_mock, *args, **kwargs)
            return result

        wrapper.__doc__ = func.__doc__
        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


@open_mock_iter(GOOD_CONFIG_FILE)
def lines_normal_test(open_mock):
    result = "".join(persistent_links.lines("Blah"))
    nose.tools.eq_(result, GOOD_CONFIG_FILE, "File content does not match.")
    open_mock.assert_called_once_with("Blah")


@raises(IOError)
@open_mock_iter("", side_effect=IOError)
def lines_bad_file_name_test(open_mock):
    "".join(persistent_links.lines("Bloop"))
    open_mock.assert_called_once_with("Bloop")


@open_mock_iter("")
def lines_empty_file_test(open_mock):
    result = "".join(persistent_links.lines("Brrap"))
    nose.tools.eq_(result, "", "Empty file not handled correctly.")
    open_mock.assert_called_once_with("Brrap")


@patch('persistent_links.lines')
def assignment_statements_non_matching_data_test(lines_mock):
    lines_mock.__iter__ = Mock(return_value=iter(['# This will not match', 'And neither = will this']))
    result = list(persistent_links.assignment_statements(lines_mock))
    assert_list_equal(list(lines_mock), [])
    assert_list_equal(result, [], "No lines should have matched.")


@patch('persistent_links.lines')
def assignment_statements_matching_data_test(lines_mock):
    lines_mock.__iter__ = Mock(return_value=iter(['A=B', 'A=C', 'ASD = JQM', ' X=345', 'K = 8ABs7 ']))
    result = list(persistent_links.assignment_statements(lines_mock))
    assert_list_equal(result, [('A', 'B'), ('A', 'C'),
                               ('ASD', 'JQM'), ('X', '345'),
                               ('K', '8ABs7')], "Some assignment lines were not recognized")


@patch('persistent_links.assignment_statements')
@patch('persistent_links.lines')
def fetch_configuration_simple_assignments_test(lines_mock, assign_mock):
    assign_mock.return_value.__iter__ = Mock(return_value=iter([('A', 'B'), ('C', 'D')]))
    lines_mock.return_value = sentinel.generator
    result = persistent_links.fetch_configuration("Blah")
    lines_mock.assert_called_once_with("Blah")
    assign_mock.assert_called_once_with(sentinel.generator)
    assert_dict_equal(result, {'A': 'B', 'C': 'D'}, "Results do not match.")


@patch('persistent_links.assignment_statements')
@patch('persistent_links.lines')
def fetch_configuration_multiple_assignments_test(lines_mock, assign_mock):
    assign_mock.return_value.__iter__ = Mock(return_value=iter([('A', 'B'), ('A', 'D')]))
    lines_mock.return_value = sentinel.generator
    result = persistent_links.fetch_configuration("Blah")
    lines_mock.assert_called_once_with("Blah")
    assign_mock.assert_called_once_with(sentinel.generator)
    assert_dict_equal(result, {'A': ['B', 'D']}, "Results do not match.")


@patch('persistent_links.assignment_statements')
@patch('persistent_links.lines')
def fetch_configuration_no_assignments_test(lines_mock, assign_mock):
    assign_mock.return_value.__iter__ = Mock(return_value=iter([]))
    lines_mock.return_value = sentinel.generator
    result = persistent_links.fetch_configuration("Blah")
    lines_mock.assert_called_once_with("Blah")
    assign_mock.assert_called_once_with(sentinel.generator)
    assert_dict_equal(result, {}, "Results do not match.")


@patch('persistent_links.assignment_statements')
@patch('persistent_links.lines')
def fetch_configuration_mixed_assignments_test(lines_mock, assign_mock):
    assign_mock.return_value.__iter__ = Mock(return_value=iter([('A', 'B'), ('C', 'D'), ('C', 'E')]))
    lines_mock.return_value = sentinel.generator
    result = persistent_links.fetch_configuration("Blah")
    lines_mock.assert_called_once_with("Blah")
    assign_mock.assert_called_once_with(sentinel.generator)
    assert_dict_equal(result, {'A': 'B', 'C': ['D', 'E']}, "Results do not match.")


@patch('os.path.getmtime')
def minutes_since_modified_no_file_test(getmtime_mock):
    getmtime_mock.side_effect = os.error
    result = persistent_links.minutes_since_modified("Foo")
    getmtime_mock.assert_called_once_with("Foo")
    nose.tools.eq_(result, sys.maxint, "Failure to return maxint when the file isn't found.")


@patch('os.path.getmtime')
def minutes_since_modified_old_file_test(getmtime_mock):
    getmtime_mock.return_value = time.time() - 60 * 30  # 30 minutes before now
    result = persistent_links.minutes_since_modified("Bar")
    getmtime_mock.assert_called_once_with("Bar")
    nose.tools.ok_(result >= 30, "Failure to return a time that is at least 30 minutes old")


@patch('os.path.getmtime')
def minutes_since_modified_one_minute_old_test(getmtime_mock):
    getmtime_mock.return_value = time.time() - 1 * 60  # 1 minute ago
    result = persistent_links.minutes_since_modified("FooBar")
    getmtime_mock.assert_called_once_with("FooBar")
    nose.tools.ok_(1 <= result <= 2, "Failure to return one minute old")


@open_mock_iter("B,XRF721  ,C,204.45.107.21,020315,11:50:03\n")
def current_links_one_active_link_test(open_mock):
    result = persistent_links.current_links(sentinel.filepath)
    open_mock.assert_called_once_with(sentinel.filepath)
    assert_dict_equal(result, {"B": ["XRF721", 'C', '204.45.107.21', '020315', '11:50:03']})


@open_mock_iter("B,XRF721  ,C,204.45.107.21,020315,11:50:03\nC,REF001  ,C,185.131.88.5,020315,11:52:01")
def current_links_multiple_active_link_test(open_mock):
    result = persistent_links.current_links(sentinel.filepath)
    open_mock.assert_called_once_with(sentinel.filepath)
    assert_dict_equal(result, {"B": ["XRF721", 'C', '204.45.107.21', '020315', '11:50:03'],
                               "C": ['REF001', 'C', '185.131.88.5', '020315', '11:52:01']})


@open_mock_iter("")
def current_links_no_active_link_test(open_mock):
    result = persistent_links.current_links(sentinel.filepath)
    open_mock.assert_called_once_with(sentinel.filepath)
    assert_dict_equal(result, {})


@open_mock_iter("", side_effect=IOError)
@raises(IOError)
def current_links_invalid_file(open_mock):
    persistent_links.current_links(sentinel.filepath)
    open_mock.assert_called_once_with(sentinel.filepath)


def rf_file_name_main_modules_test():
    config = {'RF_FLAGS_DIR': "/usr/blah"}
    nose.tools.eq_("/usr/blah/local_rf_use_A.txt", persistent_links.rf_file_name(config, 'A'),
                   "Module A file not correct")
    nose.tools.eq_("/usr/blah/local_rf_use_B.txt", persistent_links.rf_file_name(config, 'B'),
                   "Module B file not correct")
    nose.tools.eq_("/usr/blah/local_rf_use_C.txt", persistent_links.rf_file_name(config, 'C'),
                   "Module C file not correct")


def status_file_name_test():
    config = {'STATUS_FILE': '/root/g2_link/RPT_STATUS.txt'}
    nose.tools.eq_('/root/g2_link/RPT_STATUS.txt', persistent_links.status_file_name(config),
                   "Status file name incorrect.")


def persistent_links_all_modules_links_test():
    config = {'LINK_AT_STARTUP_A': 'AN0HAPC', 'LINK_AT_STARTUP_B': 'BXRF721C', 'LINK_AT_STARTUP_C': 'CNV0NA'}
    result = persistent_links.persistent_links(config)
    assert_dict_equal(result, {'A': ('A', 'N0HAP', 'C'), 'B': ('B', 'XRF721', 'C'), 'C': ('C', 'NV0N', 'A')})


def persistent_links_one_module_link_test():
    config = {'LINK_AT_STARTUP_A': '', 'LINK_AT_STARTUP_B': 'BXRF721C', 'LINK_AT_STARTUP_C': ''}
    result = persistent_links.persistent_links(config)
    assert_dict_equal(result, {'B': ('B', 'XRF721', 'C')})


def format_gateway_command_test():
    nose.tools.eq_(persistent_links.format_gateway_command('N0HAP', 'B', 'L'), "N0HAP BL", "1x3 Failure")
    nose.tools.eq_(persistent_links.format_gateway_command('KC0SIG', 'C', 'L'), "KC0SIGCL", "2x3 Failure")
    nose.tools.eq_(persistent_links.format_gateway_command('NV0N', 'A', 'L'), "NV0N  AL", "1x2 Failure")
    nose.tools.eq_(persistent_links.format_gateway_command('', '', 'U'), "       U", "Unlink Failure")


@patch('subprocess.call')
def g2link_test_success_test(call_proc):
    cmd = "%s/g2link_test" % persistent_links.G2_LINK_DIRECTORY
    config = {'TO_G2_EXTERNAL_IP': '192.168.1.2', 'MY_G2_LINK_PORT': '18998', 'LOGIN_CALL': 'W0QEY'}
    persistent_links.g2link_test(config, 'Foo', 'B', "W0QEY BL")
    call_proc.assert_called_once_with([cmd, '192.168.1.2', '18998', "Foo", 'W0QEY', 'B', '20', '2',
                                       persistent_links.ADMIN, 'W0QEY BL'])


@patch('subprocess.call')
@patch('sys.exit')
def g2link_test_success_test(exit_proc, call_proc):
    call_proc.side_effect = os.error
    cmd = "%s/g2link_test" % persistent_links.G2_LINK_DIRECTORY
    config = {'TO_G2_EXTERNAL_IP': '192.168.1.2', 'MY_G2_LINK_PORT': '18998', 'LOGIN_CALL': 'W0QEY'}
    persistent_links.g2link_test(config, 'Foo', 'B', "W0QEY BL")
    call_proc.assert_called_once_with([cmd, '192.168.1.2', '18998', "Foo", 'W0QEY', 'B', '20', '2',
                                       persistent_links.ADMIN, 'W0QEY BL'])
    exit_proc.assert_called_once_with('Could not run command %s' % cmd)


@patch('persistent_links.g2link_test')
@patch('persistent_links.format_gateway_command')
def link_test(format_mock, g2link_mock):
    config = sentinel.config
    format_mock.return_value = "XRF721CL"
    persistent_links.link(config, 'B', 'XRF721', 'C')
    format_mock.assert_called_once_with('XRF721', 'C', 'L')
    g2link_mock.assert_called_once_with(sentinel.config, "LINK", 'B', 'XRF721CL')


@patch('persistent_links.g2link_test')
@patch('persistent_links.format_gateway_command')
def unlink_test(format_mock, g2link_mock):
    config = sentinel.config
    format_mock.return_value = "       U"
    persistent_links.unlink(config, 'B')
    format_mock.assert_called_once_with('', '', 'U')
    g2link_mock.assert_called_once_with(sentinel.config, "UNLINK", 'B', '       U')


@patch('persistent_links.fetch_configuration')
@patch('persistent_links.persistent_links')
@patch('persistent_links.minutes_since_modified')
@patch('persistent_links.link')
@patch('persistent_links.unlink')
@patch('persistent_links.status_file_name')
@patch('persistent_links.current_links')
@patch('sys.stdout', new_callable=StringIO)
@patch.dict('persistent_links.RF_TIMERS', values={'A': 15, 'B': 20, 'C': 10})
@patch('persistent_links.G2_LINK_DIRECTORY', new='/root/g2_link')
def main_nothing_to_do_test(mock_out, mock_current_links, mock_status_file_name,
                            mock_unlink, mock_link, mock_minutes, mock_persistent_links, mock_fetch_config):
    mock_current_links.return_value = {'B': ['XRF721', 'C', '204.45.107.21', '020315', '11:50:03']}
    mock_status_file_name.return_value = sentinel.status_file_name
    mock_fetch_config.return_value = {'RF_FLAGS_DIR': '/tmp'}
    mock_persistent_links.return_value = {'B': ('B', 'XRF721', 'C')}
    mock_minutes.return_value = 400

    persistent_links.main()

    nose.tools.eq_(mock_link.called, False, "Link should not have been called.")
    nose.tools.eq_(mock_unlink.called, False, "Unlink should not have been called.")
    assert_regexp_matches(mock_out.getvalue(), "Nothing to do",
                          "Message did not signal that nothing was to be done.")
    mock_fetch_config.assert_called_once_with('/root/g2_link/g2_link.cfg')
    mock_persistent_links.assert_called_once_with(mock_fetch_config.return_value)
    mock_minutes.assert_called_once_with('/tmp/local_rf_use_B.txt')


@patch('persistent_links.fetch_configuration')
@patch('persistent_links.persistent_links')
@patch('persistent_links.minutes_since_modified')
@patch('persistent_links.link')
@patch('persistent_links.unlink')
@patch('persistent_links.status_file_name')
@patch('persistent_links.current_links')
@patch('sys.stdout', new_callable=StringIO)
@patch.dict('persistent_links.RF_TIMERS', values={'A': 15, 'B': 20, 'C': 10})
@patch('persistent_links.G2_LINK_DIRECTORY', new='/root/g2_link')
def main_establish_link_test(mock_out, mock_current_links, mock_status_file_name,
                             mock_unlink, mock_link, mock_minutes, mock_persistent_links, mock_fetch_config):
    mock_current_links.return_value = {}
    mock_status_file_name.return_value = sentinel.status_file_name
    mock_fetch_config.return_value = {'RF_FLAGS_DIR': '/tmp'}
    mock_persistent_links.return_value = {'B': ('B', 'XRF721', 'C')}
    mock_minutes.return_value = 400

    persistent_links.main()

    mock_link.assert_called_once_with(mock_fetch_config.return_value, 'B', 'XRF721', 'C')
    nose.tools.eq_(mock_unlink.called, False, "Unlink should not have been called.")
    assert_regexp_matches(mock_out.getvalue(), "Establish persistent link for module B",
                          "Did not indicate establishing link for module B")
    mock_fetch_config.assert_called_once_with('/root/g2_link/g2_link.cfg')
    mock_persistent_links.assert_called_once_with(mock_fetch_config.return_value)
    mock_minutes.assert_called_once_with('/tmp/local_rf_use_B.txt')


@patch('persistent_links.fetch_configuration')
@patch('persistent_links.persistent_links')
@patch('persistent_links.minutes_since_modified')
@patch('persistent_links.link')
@patch('persistent_links.unlink')
@patch('persistent_links.status_file_name')
@patch('persistent_links.current_links')
@patch('sys.stdout', new_callable=StringIO)
@patch.dict('persistent_links.RF_TIMERS', values={'A': 15, 'B': 20, 'C': 10})
@patch('persistent_links.G2_LINK_DIRECTORY', new='/root/g2_link')
def main_local_machine_active_test(mock_out, mock_current_links, mock_status_file_name,
                                   mock_unlink, mock_link, mock_minutes, mock_persistent_links, mock_fetch_config):
    mock_current_links.return_value = {}
    mock_status_file_name.return_value = sentinel.status_file_name
    mock_fetch_config.return_value = {'RF_FLAGS_DIR': '/tmp'}
    mock_persistent_links.return_value = {'B': ('B', 'XRF721', 'C')}
    mock_minutes.return_value = 4

    persistent_links.main()

    nose.tools.eq_(mock_link.called, False, "Link should not have been called.")
    nose.tools.eq_(mock_unlink.called, False, "Unlink should not have been called.")
    assert_regexp_matches(mock_out.getvalue(), "The gateway for module B is being used",
                          "Did not indicate local RF traffic")
    mock_fetch_config.assert_called_once_with('/root/g2_link/g2_link.cfg')
    mock_persistent_links.assert_called_once_with(mock_fetch_config.return_value)
    mock_minutes.assert_called_once_with('/tmp/local_rf_use_B.txt')


@patch('persistent_links.fetch_configuration')
@patch('persistent_links.persistent_links')
@patch('persistent_links.minutes_since_modified')
@patch('persistent_links.link')
@patch('persistent_links.unlink')
@patch('persistent_links.status_file_name')
@patch('persistent_links.current_links')
@patch('sys.stdout', new_callable=StringIO)
@patch.dict('persistent_links.RF_TIMERS', values={'A': 15, 'B': 20, 'C': 10})
@patch('persistent_links.G2_LINK_DIRECTORY', new='/root/g2_link')
def main_unlink_other_and_establish_persistent_link_test(mock_out, mock_current_links, mock_status_file_name,
                                                         mock_unlink, mock_link, mock_minutes, mock_persistent_links,
                                                         mock_fetch_config):
    mock_current_links.return_value = {'B': ['REF001', 'C', '178.45.107.21', '020315', '11:50:03']}
    mock_status_file_name.return_value = sentinel.status_file_name
    mock_fetch_config.return_value = {'RF_FLAGS_DIR': '/tmp'}
    mock_persistent_links.return_value = {'B': ('B', 'XRF721', 'C')}
    mock_minutes.return_value = 400

    persistent_links.main()

    mock_unlink.called_once_with(mock_fetch_config.return_value, 'B')
    mock_link.assert_called_once_with(mock_fetch_config.return_value, 'B', 'XRF721', 'C')
    assert_regexp_matches(mock_out.getvalue(),
                          "Unlinking from REF001 and establishing persistent link for module B to "
                          "XRF721, module C",
                          "Did not indicate unlinking and re-linking")
    mock_fetch_config.assert_called_once_with('/root/g2_link/g2_link.cfg')
    mock_persistent_links.assert_called_once_with(mock_fetch_config.return_value)
    mock_minutes.assert_called_once_with('/tmp/local_rf_use_B.txt')


@patch('persistent_links.fetch_configuration')
@patch('persistent_links.persistent_links')
@patch('persistent_links.minutes_since_modified')
@patch('persistent_links.link')
@patch('persistent_links.unlink')
@patch('persistent_links.status_file_name')
@patch('persistent_links.current_links')
@patch('sys.stdout', new_callable=StringIO)
@patch.dict('persistent_links.RF_TIMERS', values={'A': 15, 'B': 20, 'C': 10})
def main_multiple_actions_required_test(mock_out, mock_current_links, mock_status_file_name,
                                        mock_unlink, mock_link, mock_minutes, mock_persistent_links, mock_fetch_config):
    mock_current_links.return_value = {'A': ['REF003', 'B', '127.201.100.1', '010516', '12:00:00'],
                                       'B': ['REF001', 'C', '178.45.107.21', '020315', '11:50:03']}
    mock_status_file_name.return_value = sentinel.status_file_name
    mock_fetch_config.return_value = {'RF_FLAGS_DIR': '/tmp'}
    mock_persistent_links.return_value = {'A': ('A', 'REF003', 'B'),
                                          'B': ('B', 'XRF721', 'C'),
                                          'C': ('C', 'REF008', 'A')}

    mock_minutes.side_effect = lambda x: {'/tmp/local_rf_use_A.txt': 20, '/tmp/local_rf_use_B.txt': 21,
                                          '/tmp/local_rf_use_C.txt': 9}[x]

    persistent_links.main()

    mock_unlink.called_once_with(mock_fetch_config.return_value, 'B')
    mock_link.assert_called_once_with(mock_fetch_config.return_value, 'B', 'XRF721', 'C')
    assert_regexp_matches(mock_out.getvalue(),
                          "Nothing to do - persistent link already established for module A",
                          "Nothing should be done for module A, as it is already linked correctly.")
    assert_regexp_matches(mock_out.getvalue(),
                          "Unlinking from REF001 and establishing persistent link for module B to XRF721, "
                          "module C",
                          "Should unlink from REF001 on module B and establish a persistent link to "
                          "XRF721, module C")
    assert_regexp_matches(mock_out.getvalue(),
                          "The gateway for module C is being used locally",
                          "A link should not be established for module C, because the machine "
                          "is being used locally on that module.")
    mock_fetch_config.assert_called_once_with('/root/g2_link/g2_link.cfg')
    mock_persistent_links.assert_called_once_with(mock_fetch_config.return_value)
    mock_minutes.assert_has_calls([call('/tmp/local_rf_use_A.txt'), call('/tmp/local_rf_use_B.txt'),
                                   call('/tmp/local_rf_use_C.txt')], any_order=True)


if __name__ == "__main__":
    nose.main()