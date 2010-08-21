# -*- coding: utf-8 -*-
# Copyright (C) 2010 Sebastian Wiesner <lunaryorn@googlemail.com>

# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation; either version 2.1 of the License, or (at your
# option) any later version.

# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License
# for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation,
# Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA


import sys
import random
import subprocess

import udev


def _read_udev_database(properties_blacklist):
    udevadm = subprocess.Popen(['udevadm', 'info', '--export-db'],
                               stdout=subprocess.PIPE)
    database = udevadm.communicate()[0].splitlines()
    devices = {}
    current_properties = None
    for line in database:
        line = line.strip()
        if not line:
            continue
        type, value = line.split(': ', 1)
        value = value.decode(sys.getfilesystemencoding())
        if type == 'P':
            current_properties = devices.setdefault(value, {})
        elif type == 'E':
            property, value = value.split('=', 1)
            if property in properties_blacklist:
                continue
            current_properties[property] = value
    return devices


def get_device_sample(config):
    if config.getvalue('all_devices'):
        return config.udev_database
    else:
        device_sample_size = config.getvalue('device_sample_size')
        actual_size = min(device_sample_size, len(config.udev_database))
        return random.sample(config.udev_database, actual_size)


def pytest_namespace():
    return dict(get_device_sample=get_device_sample)


def pytest_addoption(parser):
    parser.addoption('--all-devices', action='store_true',
                     help='Run device tests against *all* devices in the '
                     'database.  By default, only a random sample will be '
                     'checked.', default=False)
    parser.addoption('--device-sample-size', type='int', metavar='N',
                     help='Use a random sample of N elements (default: 10)',
                     default=10)

def pytest_configure(config):
    # these are volatile, frequently changing properties, which lead to
    # bogus failures during test_device_property, and therefore they are
    # masked and shall be ignored for test runs.
    config.properties_backlist = frozenset(
        ['POWER_SUPPLY_CURRENT_NOW', 'POWER_SUPPLY_VOLTAGE_NOW',
         'POWER_SUPPLY_CHARGE_NOW'])
    config.udev_database = _read_udev_database(config.properties_backlist)


def pytest_funcarg__database(request):
    """
    The complete udev database parsed from the output of ``udevadm info
    --export-db``.

    Return a dictionary, mapping the devpath of a device *without* sysfs
    mountpoint to a dictionary of properties of the device.
    """
    return request.config.udev_database


def pytest_funcarg__context(request):
    """
    Return a useable :class:`udev.Context` object.  The context is cached
    with session scope.
    """
    return request.cached_setup(setup=udev.Context, scope='session')

def pytest_funcarg__device_path(request):
    """
    Return a device path as string.

    The device path must be available as ``request.param``.
    """
    return request.param

def pytest_funcarg__all_properties(request):
    """
    Get all properties from the exported database (as returned by the
    ``database`` funcarg) of the device pointed to by the ``device_path``
    funcarg.
    """
    device_path = request.getfuncargvalue('device_path')
    return dict(request.getfuncargvalue('database')[device_path])

def pytest_funcarg__properties(request):
    """
    Same as the ``all_properties`` funcarg, but with the special ``DEVNAME``
    property removed.
    """
    properties = request.getfuncargvalue('all_properties')
    properties.pop('DEVNAME', None)
    return properties

def pytest_funcarg__sys_path(request):
    """
    Return the sys_path including the sysfs mountpoint for the device path
    returned by the ``device_path`` funcarg.
    """
    context = request.getfuncargvalue('context')
    device_path = request.getfuncargvalue('device_path')
    return context.sys_path + device_path

def pytest_funcarg__device(request):
    """
    Create and return a :class:`udev.Device` object for the sys_path
    returned by the ``sys_path`` funcarg, and the context from the
    ``context`` funcarg.
    """
    sys_path = request.getfuncargvalue('sys_path')
    context = request.getfuncargvalue('context')
    return udev.Device.from_sys_path(context, sys_path)