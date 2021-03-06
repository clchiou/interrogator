# Copyright (c) 2013 Che-Liang Chiou

'''Interrogate Android NDK to get build information.'''

from cStringIO import StringIO
import contextlib
import errno
import os
import shutil
import subprocess
import tempfile

__all__ = ['interrogate']


class Interrogator:
    '''Interrogate Android NDK to get build information.'''

    STATIC_LIBRARY = 'BUILD_STATIC_LIBRARY'
    SHARED_LIBRARY = 'BUILD_SHARED_LIBRARY'
    EXECUTABLE = 'BUILD_EXECUTABLE'
    BUILD_TYPES = frozenset((STATIC_LIBRARY, SHARED_LIBRARY, EXECUTABLE))

    MODULE = 'InterrogateActivity'

    def __init__(self, interrogate_room, android_ndk):
        '''Set up build environment for interrogating Android NDK.'''
        if not os.path.exists(android_ndk):
            raise RuntimeError('Could not find NDK at %s' % android_ndk)
        self.interrogate_room = interrogate_room
        self.android_ndk = android_ndk
        self.build_type = None
        self.android_vars = None
        self.application_vars = None
        # Make Makefile
        makefile = '''# Makefile
include {android_ndk}/build/core/build-local.mk

interrogate:
\t@echo TARGET_CCFLAGS=$(call get-src-file-target-cflags,{module}.cpp)
\t@echo TARGET_CC=$(TARGET_CC)
\t@echo TARGET_CFLAGS=$(TARGET_CFLAGS)
\t@echo TARGET_CPP=$(TARGET_CPP)
\t@echo TARGET_CPPFLAGS=$(TARGET_CPPFLAGS)
\t@echo TARGET_CXX=$(TARGET_CXX)
\t@echo TARGET_CXXFLAGS=$(TARGET_CXXFLAGS)
\t@echo TARGET_LD=$(TARGET_LD)
\t@echo TARGET_LDFLAGS=$(TARGET_LDFLAGS)
\t@echo TARGET_AR=$(TARGET_AR)
\t@echo TARGET_ARFLAGS=$(TARGET_ARFLAGS)
\t@echo TARGET_STRIP=$(TARGET_STRIP)
\t@echo TARGET_OBJCOPY=$(TARGET_OBJCOPY)
\t@echo LOCAL_CFLAGS=$(LOCAL_CFLAGS)
\t@echo LOCAL_CPPFLAGS=$(LOCAL_CPPFLAGS)
\t@echo LOCAL_CXXFLAGS=$(LOCAL_CXXFLAGS)
\t@echo NDK_APP_CFLAGS=$(NDK_APP_CFLAGS)
\t@echo NDK_APP_CPPFLAGS=$(NDK_APP_CPPFLAGS)
\t@echo NDK_APP_CXXFLAGS=$(NDK_APP_CXXFLAGS)
\t@echo C_INCLUDES=$(TARGET_C_INCLUDES) \\
\t\t$(call module-get-listed-export,\\
\t\t$(call module-get-all-dependencies,{module}),C_INCLUDES)

.PHONY: interrogate
'''
        makefile = makefile.format(android_ndk=self.android_ndk,
                                   module=self.MODULE)
        create_file(os.path.join(self.interrogate_room, 'Makefile'), makefile)

    def question(self,
                 build_type=STATIC_LIBRARY, android_vars=None,
                 application_vars=None):
        '''Question NDK for specific build information.'''
        self.set_android_vars(build_type, android_vars)
        self.set_application_vars(application_vars)
        # Now, question NDK!
        cmd = 'make interrogate'.split()
        output = subprocess.check_output(cmd, cwd=self.interrogate_room)
        for line in StringIO(output):
            name, value = line.split('=', 1)
            value = value.strip()
            yield name, value

    def set_android_vars(self, build_type=STATIC_LIBRARY, android_vars=None):
        '''Set build variables in Android.mk.'''
        assert build_type in self.BUILD_TYPES
        if (self.build_type == build_type and
                self.android_vars is not None and android_vars is None):
            return
        self.build_type = build_type
        self.android_vars = android_vars
        # Make Android.mk
        android_mk = StringIO()
        android_mk.write('# Android.mk\n')
        android_mk.write('LOCAL_PATH := $(call my-dir)\n')
        android_mk.write('include $(CLEAR_VARS)\n')
        android_mk.write('LOCAL_MODULE := %s\n' % self.MODULE)
        android_mk.write('LOCAL_SRC_FILES := %s.cpp\n' % self.MODULE)
        if self.android_vars:
            for name in self.android_vars:
                android_mk.write('%s := %s\n' %
                                 (name, self.android_vars[name]))
        android_mk.write('include $(%s)\n' % self.build_type)
        create_file(os.path.join(self.interrogate_room, 'jni/Android.mk'),
                    android_mk.getvalue())

    def set_application_vars(self, application_vars):
        '''Set build variables in Application.mk.'''
        if self.application_vars is not None and application_vars is None:
            return
        self.application_vars = application_vars
        # Make Application.mk
        application_mk = StringIO()
        application_mk.write('# Application.mk\n')
        if self.application_vars:
            for name in self.application_vars:
                application_mk.write('%s := %s\n' %
                                     (name, self.application_vars[name]))
        create_file(os.path.join(self.interrogate_room, 'jni/Application.mk'),
                    application_mk.getvalue())


@contextlib.contextmanager
def interrogate(android_ndk):
    '''Interrogate Android NDK build system.'''
    android_ndk = os.path.abspath(android_ndk)
    with create_temporary_directory() as interrogate_room:
        yield Interrogator(interrogate_room, android_ndk)


@contextlib.contextmanager
def create_temporary_directory(*args):
    '''Create a temporary directory and remove it after use.
    See tempfile.mkdtemp() for argument documentation.
    '''
    path = tempfile.mkdtemp(*args)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def create_file(path, contents):
    '''Create a file at path and write contents to it.'''
    try:
        os.makedirs(os.path.dirname(path))
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
    with open(path, 'w') as fout:
        fout.write(contents)


if __name__ == '__main__':
    # Sample usage of Interrogator
    import sys
    with interrogate(sys.argv[1]) as _interrogator:
        _interrogator.set_application_vars(application_vars={
            'APP_OPTIM': 'release',
            'API_ABI': 'armeabi',
            'API_PLATFORM': 'android-3',
        })
        _interrogator.set_android_vars(build_type=Interrogator.STATIC_LIBRARY,
                                       android_vars={'LOCAL_ARM_MODE': 'arm'})
        for _name, _value in _interrogator.question():
            print '%s=%s' % (_name, _value)
