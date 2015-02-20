#!/usr/bin/env python2
"""Script to maintain persistent links on Free Star* (D-STAR) systems.
"""

# persistent_links.py - Script to maintain persistent links on Free Star* (D-STAR) systems.
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

import re
import datetime
import os
import time
import csv
import subprocess
import sys

# These variables may be configured for a particular installation.
# G2_LINK_DIRECTORY - should be the full path to the directory where the g2_link program, its configuration files,
# and utilities are installed.
# RF_TIMERS         - This specifies the number of minutes that each module should be idle (i.e., no local RF traffic)
#                     before a persistent link is restored.
# ADMIN             - The callsign of the administrator - this callsign will be used when issuing commands to the
#                     g2_link system via its command-line utility.

G2_LINK_DIRECTORY = "/root/g2_link"
RF_TIMERS = {'A': 15, 'B': 20, 'C': 10}
ADMIN = "N0HAP"


def lines(file_name):
    """
    Generator which produces lines of a file, one at a time.
    :param file_name: The file name, including the full path.
    :return: Yields string lines of the file, one at a time.
    """
    # Could not use with open(file_name) as f: ... since this must run on Python 2.4
    f = open(file_name)
    try:
        for line in f:
            yield line
    except:
        f.close()
    f.close()


def assignment_statements(gen):
    """
    Generator producing tuples containing the left and right hand sides of assignment, for each line that contains
    assignment.
    :param gen: The generator that produces lines to be tested
    :return: Yields tuples containing the left and right hand sides of an assignment.
    """
    assignment = re.compile('^\s*(\w+)\s*=\s*(\S*)\s*\Z')

    for line in gen:
        m = assignment.match(line)
        if m:
            yield m.groups()


def fetch_configuration(file_name):
    """
    Parses a g2_link configuration file and produces a dictionary containing all variable values. Overlapping
    assignments result in a right hand side (dictionary value) which is a list of values.
    :param file_name: The file name, including the full path.
    :return: Dictionary containing variable names (keys) and assigned values
    """
    config = {}
    for (k, v) in assignment_statements(lines(file_name)):
        if k in config:
            if type(config[k]) is not list:
                config[k] = [config[k]]
            config[k].append(v)
        else:
            config[k] = v

    return config


def minutes_since_modified(file_name):
    """Calculates the number of minutes since a file was last modified, or produces a large number if the file
    doesn't exist.
    :param file_name: The file name, including the full path.
    :return: Number of minutes (floating point)
    """
    try:
        return (time.time() - os.path.getmtime(file_name)) / 60
    except os.error:
        return sys.maxint


def current_links(file_name):
    """
    Produces a dictionary containing the the modules (keys) and the information associated with the linked reflector
    :param file_name: File name, including path, of the repeater status file.
    :return: Dictionary containing module (key) and tuple value of linked machine.  If a module is not linked,
    there will be no entry for that module.  The link information includes the callsign/reflector id, remote port,
    ip address, date, and time.
    """
    links = {}
    # Could not use with open(file_name) as f: ... since this must run on Python 2.4
    f = open(file_name)
    try:
        for items in csv.reader(f):
            if len(items) > 0:
                links[items[0]] = map(str.strip, items[1:])
    except:
        f.close()
        raise
    f.close()
    return links


def rf_file_name(config, module):
    """
    Produces the full path to the rf local use file for a particular module
    :param config: Dictionary containing the configuration variables for the g2_link system
    :param module: Single letter module identifier (e.g., A, B, C)
    :return: The file name, including the full path, for the rf local use file.
    """
    return os.path.join(config["RF_FLAGS_DIR"], "local_rf_use_%s.txt" % module)


def status_file_name(config):
    """
    Produces the full path and file name for the repeater status file, where active links are stored.
    :param config: Dictionary containing the configuration variables for the g2_link system
    :return: The file name, including the full path, for the repeater status file.
    """
    return config["STATUS_FILE"]


def persistent_links(config):
    """
    Produces a mapping (dictionary) of modules to machines that should be persistently linked.
    :param config: Dictionary containing the configuration variables for the g2_link system
    :return: Dictionary containing desired persistent links by module.  If there is no persistent link
    expressed for a module, there is no entry for that module in the dictionary.  The returned tuple
    for a link is (local module, destination machine, destination module).
    """
    p_links = {}
    for module in ('A', 'B', 'C'):
        k = "LINK_AT_STARTUP_%s" % module
        if k in config and config[k] != "":
            p_links[module] = (config[k][0], config[k][1:-1], config[k][-1:])
    return p_links


def format_gateway_command(callsign, remote_module, command):
    """
    Produces a valid URCALL string, given a callsign, remote module and single letter command.
    :param callsign: The reflector or callsign for the URCALL command
    :param remote_module: The single letter module identifier
    :param command: The single letter command (e.g., L for link)
    :return: A valid URCALL 8-character string
    """
    return "%-6s%1s%s" % (callsign, remote_module, command)


def g2link_test(config, cmd, local_module, gateway_command):
    """
    Calls the g2_link command utility to control the g2_link system.
    :param config: Dictionary containing the configuration variables for the g2_link system
    :param cmd: Word that indicates the command type (i.e., LINK, UNLINK, HELLO)
    :param local_module: The single letter local module identifier
    :param gateway_command: A URCALL compliant 8-character string
    :return: The return code of the subprocess that is executed
    """
    g2_link_test_cmd = os.path.join(G2_LINK_DIRECTORY, "g2link_test")
    ip = config["TO_G2_EXTERNAL_IP"]
    port = config["MY_G2_LINK_PORT"]
    gateway_callsign = config["LOGIN_CALL"]
    try:
        return subprocess.call(
            [g2_link_test_cmd, ip, port, cmd, gateway_callsign, local_module, "20", "2", ADMIN, gateway_command])
    except os.error:
        sys.exit("Could not run command %s" % g2_link_test_cmd)


def link(config, local_module, callsign, remote_module):
    """
    Calls the g2_link command utility to link from a local module to a particular reflector/callsign remote module
    :param config: Dictionary containing the configuration variables for the g2_link system.
    :param local_module: The single letter module identifier for our local system
    :param callsign: The callsign or reflector identifier to which we will link
    :param remote_module: The remote module for the link
    :return: The return code from the subprocess.
    """
    return g2link_test(config, "LINK", local_module, format_gateway_command(callsign, remote_module, "L"))


def unlink(config, local_module):
    """
    Calls the g2_link command utility to unlink a local module.
    :param config: Dictionary containing the configuration variables for the g2_link system.
    :param local_module: The single letter module identifier for our local system
    :return: The return code from the subprocess
    """
    return g2link_test(config, "UNLINK", local_module, format_gateway_command("", "", "U"))


def main():
    """
    Establishes persistent links for each module where a desired persistent link exists, if needed and
    if there has been no local traffic for the requisite amount of time.
    :return: 0, if successful
    """
    config = fetch_configuration(os.path.join(G2_LINK_DIRECTORY, "g2_link.cfg"))

    p_links = persistent_links(config)

    print '------------------------------------------'
    print datetime.datetime.today()

    # For each module that has a persistent link specified
    #     If the gateway is being used locally, don't do anything
    #     Otherwise, we should ensure we are linked to the correct, persistent link, assuming
    #     the machine has been inactive long enough and is not already linked to the desired target.

    for module in p_links.keys():
        if minutes_since_modified(rf_file_name(config, module)) < RF_TIMERS[module]:
            print "The gateway for module %s is being used locally - don't do anything" % module
        else:
            links = current_links(status_file_name(config))
            if not module in links:
                print "Establish persistent link for module %s" % module
                link(config, module, p_links[module][1], p_links[module][2])
            elif links[module][0] != p_links[module][1]:
                print "Unlinking from %s and establishing persistent link for module %s to %s, module %s" % (
                    links[module][0], module, p_links[module][1], p_links[module][2])
                unlink(config, module)
                link(config, module, p_links[module][1], p_links[module][2])
            else:
                print "Nothing to do - persistent link already established for module %s." % module
    return 0


if __name__ == '__main__':

    sys.exit(main())
